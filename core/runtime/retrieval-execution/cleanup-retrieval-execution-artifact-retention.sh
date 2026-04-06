#!/usr/bin/env bash
set -euo pipefail

export GIT_PAGER=cat
export PAGER=cat

ROOT="/home/agent/agents"
STAMP="$(date +%Y-%m-%d-%H%M%S)"
MODE="${1:-plan}"

KEEP_RETRIEVAL="${KEEP_RETRIEVAL:-12}"
KEEP_REGRESS="${KEEP_REGRESS:-8}"
KEEP_FULL="${KEEP_FULL:-8}"

OUTDIR="${ROOT}/core/artifacts/maintenance/retrieval-execution-retention/${STAMP}"
PLAN_FILE="${OUTDIR}/retention-plan.txt"
SUMMARY_FILE="${OUTDIR}/SUMMARY.md"

mkdir -p "${OUTDIR}"

is_timestamp_dir() {
  local name="$1"
  [[ "${name}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{6}$ ]]
}

has_tracked_files() {
  local rel="$1"
  git -C "${ROOT}" ls-files -- "${rel}" | grep -q .
}

latest_target_rel() {
  local link_rel="$1"
  local link_abs="${ROOT}/${link_rel}"

  if [[ -L "${link_abs}" ]]; then
    realpath --relative-to="${ROOT}" "$(readlink -f "${link_abs}")"
    return 0
  fi

  return 1
}

list_dirs_sorted() {
  local root_rel="$1"
  local root_abs="${ROOT}/${root_rel}"

  if [[ ! -d "${root_abs}" ]]; then
    return 0
  fi

  find "${root_abs}" -mindepth 1 -maxdepth 1 -type d | sort
}

build_recent_map() {
  local root_rel="$1"
  local keep_count="$2"
  local tmp_file="$3"

  : > "${tmp_file}"

  mapfile -t dirs < <(list_dirs_sorted "${root_rel}")

  if [[ "${#dirs[@]}" -eq 0 ]]; then
    return 0
  fi

  local start=0
  if (( ${#dirs[@]} > keep_count )); then
    start=$(( ${#dirs[@]} - keep_count ))
  fi

  local i
  for (( i=start; i<${#dirs[@]}; i++ )); do
    realpath --relative-to="${ROOT}" "${dirs[$i]}" >> "${tmp_file}"
  done
}

in_recent_map() {
  local rel="$1"
  local tmp_file="$2"
  grep -Fxq "${rel}" "${tmp_file}"
}

process_root() {
  local root_rel="$1"
  local latest_link_rel="$2"
  local keep_count="$3"

  local latest_rel=""
  local recent_file
  recent_file="$(mktemp)"

  if latest_rel="$(latest_target_rel "${latest_link_rel}" 2>/dev/null)"; then
    :
  else
    latest_rel=""
  fi

  build_recent_map "${root_rel}" "${keep_count}" "${recent_file}"

  echo "ROOT=${root_rel}" >> "${PLAN_FILE}"
  echo "KEEP_COUNT=${keep_count}" >> "${PLAN_FILE}"
  echo "LATEST_LINK=${latest_link_rel}" >> "${PLAN_FILE}"
  echo "LATEST_TARGET=${latest_rel:-missing}" >> "${PLAN_FILE}"

  local total=0
  local keep=0
  local delete=0

  mapfile -t dirs < <(list_dirs_sorted "${root_rel}")

  local dir_abs dir_rel base reason action
  for dir_abs in "${dirs[@]}"; do
    dir_rel="$(realpath --relative-to="${ROOT}" "${dir_abs}")"
    base="$(basename "${dir_abs}")"
    reason=""

    total=$(( total + 1 ))

    if ! is_timestamp_dir "${base}"; then
      reason="non_timestamp"
      action="KEEP"
      keep=$(( keep + 1 ))
    elif [[ -n "${latest_rel}" && "${dir_rel}" == "${latest_rel}" ]]; then
      reason="latest_target"
      action="KEEP"
      keep=$(( keep + 1 ))
    elif in_recent_map "${dir_rel}" "${recent_file}"; then
      reason="recent_window"
      action="KEEP"
      keep=$(( keep + 1 ))
    elif has_tracked_files "${dir_rel}"; then
      reason="tracked_in_git"
      action="KEEP"
      keep=$(( keep + 1 ))
    else
      reason="old_untracked"
      action="DELETE"
      delete=$(( delete + 1 ))
    fi

    echo "${action} | ${reason} | ${dir_rel}" >> "${PLAN_FILE}"

    if [[ "${MODE}" == "apply" && "${action}" == "DELETE" ]]; then
      rm -rf "${ROOT:?}/${dir_rel}"
      echo "APPLIED_DELETE=${dir_rel}"
    fi
  done

  echo "TOTAL=${total}" >> "${PLAN_FILE}"
  echo "KEEP=${keep}" >> "${PLAN_FILE}"
  echo "DELETE=${delete}" >> "${PLAN_FILE}"
  echo >> "${PLAN_FILE}"

  rm -f "${recent_file}"

  echo "${root_rel}|${total}|${keep}|${delete}" >> "${OUTDIR}/summary-counts.txt"
}

process_root "core/artifacts/retrieval-execution" "core/artifacts/retrieval-execution/latest" "${KEEP_RETRIEVAL}"
process_root "core/artifacts/retrieval-execution-canonical-regress" "core/artifacts/retrieval-execution-canonical-regress/latest" "${KEEP_REGRESS}"
process_root "core/artifacts/retrieval-execution-canonical-full-regress" "core/artifacts/retrieval-execution-canonical-full-regress/latest" "${KEEP_FULL}"

retrieval_line="$(grep '^core/artifacts/retrieval-execution|' "${OUTDIR}/summary-counts.txt" || true)"
regress_line="$(grep '^core/artifacts/retrieval-execution-canonical-regress|' "${OUTDIR}/summary-counts.txt" || true)"
full_line="$(grep '^core/artifacts/retrieval-execution-canonical-full-regress|' "${OUTDIR}/summary-counts.txt" || true)"

retrieval_total="$(echo "${retrieval_line}" | awk -F'|' '{print $2}')"
retrieval_keep="$(echo "${retrieval_line}" | awk -F'|' '{print $3}')"
retrieval_delete="$(echo "${retrieval_line}" | awk -F'|' '{print $4}')"

regress_total="$(echo "${regress_line}" | awk -F'|' '{print $2}')"
regress_keep="$(echo "${regress_line}" | awk -F'|' '{print $3}')"
regress_delete="$(echo "${regress_line}" | awk -F'|' '{print $4}')"

full_total="$(echo "${full_line}" | awk -F'|' '{print $2}')"
full_keep="$(echo "${full_line}" | awk -F'|' '{print $3}')"
full_delete="$(echo "${full_line}" | awk -F'|' '{print $4}')"

cat > "${SUMMARY_FILE}" <<EOF
# Retrieval Execution Artifact Retention

- Generated at: ${STAMP}
- Mode: ${MODE}
- Root: ${ROOT}

## Rules

- Keep latest symlink targets
- Keep newest retrieval-execution directories: ${KEEP_RETRIEVAL}
- Keep newest canonical-regress directories: ${KEEP_REGRESS}
- Keep newest canonical-full-regress directories: ${KEEP_FULL}
- Keep any directory that contains tracked git files
- Delete only old untracked timestamp directories

## Results

### retrieval-execution
- total: ${retrieval_total:-0}
- keep: ${retrieval_keep:-0}
- delete: ${retrieval_delete:-0}

### canonical-regress
- total: ${regress_total:-0}
- keep: ${regress_keep:-0}
- delete: ${regress_delete:-0}

### canonical-full-regress
- total: ${full_total:-0}
- keep: ${full_keep:-0}
- delete: ${full_delete:-0}

## Files

- Plan: ${PLAN_FILE}
- Summary: ${SUMMARY_FILE}

## Notes

This script is intentionally conservative.

It does not delete:
- tracked directories,
- latest targets,
- recent directories inside the retention window.

Use mode "plan" first, then mode "apply" only after reviewing the plan file.
EOF

echo "RETENTION_OUTDIR=${OUTDIR}"
echo "PLAN_FILE=${PLAN_FILE}"
echo "SUMMARY_FILE=${SUMMARY_FILE}"
echo
sed -n '1,220p' "${SUMMARY_FILE}"
echo
echo "PLAN_PREVIEW_BEGIN"
sed -n '1,220p' "${PLAN_FILE}"
echo "PLAN_PREVIEW_END"