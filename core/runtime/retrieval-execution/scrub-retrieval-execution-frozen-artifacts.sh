#!/usr/bin/env bash
set -euo pipefail

export GIT_PAGER=cat
export PAGER=cat

ROOT="/home/agent/agents"
STAMP="$(date +%Y-%m-%d-%H%M%S)"
MODE="${1:-plan}"

OUTDIR="${ROOT}/core/artifacts/maintenance/retrieval-execution-frozen-scrub/${STAMP}"
REPORT_FILE="${OUTDIR}/scrub-report.txt"
SUMMARY_FILE="${OUTDIR}/SUMMARY.md"

mkdir -p "${OUTDIR}"

LATEST_LINK_REL="core/artifacts/retrieval-execution/latest"
LATEST_TARGET_REL=""
if [[ -L "${ROOT}/${LATEST_LINK_REL}" ]]; then
  LATEST_TARGET_REL="$(realpath --relative-to="${ROOT}" "$(readlink -f "${ROOT}/${LATEST_LINK_REL}")")"
fi

current_status_block() {
  local rel="$1"
  git -C "${ROOT}" --no-pager status --short -- "${rel}" || true
}

mapfile -t tracked_items < <(
  git -C "${ROOT}" ls-files 'core/artifacts/retrieval-execution/*' \
    | awk -F/ 'NF>=4 {print $1"/"$2"/"$3"/"$4}' \
    | sort -u
)

tracked_count="${#tracked_items[@]}"
latest_symlink_skipped=0
latest_target_skipped=0
clean_count=0
dirty_count=0
applied_clean_count=0
applied_residual_count=0

{
  echo "MODE=${MODE}"
  echo "ROOT=${ROOT}"
  echo "LATEST_LINK=${LATEST_LINK_REL}"
  echo "LATEST_TARGET=${LATEST_TARGET_REL:-missing}"
  echo
} > "${REPORT_FILE}"

for item_rel in "${tracked_items[@]}"; do
  if [[ "${item_rel}" == "${LATEST_LINK_REL}" ]]; then
    echo "KEEP_LATEST_SYMLINK | ${item_rel}" >> "${REPORT_FILE}"
    latest_symlink_skipped=$(( latest_symlink_skipped + 1 ))
    continue
  fi

  if [[ -n "${LATEST_TARGET_REL}" && "${item_rel}" == "${LATEST_TARGET_REL}" ]]; then
    echo "KEEP_LATEST_TARGET | ${item_rel}" >> "${REPORT_FILE}"
    latest_target_skipped=$(( latest_target_skipped + 1 ))
    continue
  fi

  status_before="$(current_status_block "${item_rel}")"

  if [[ -z "${status_before}" ]]; then
    echo "CLEAN | ${item_rel}" >> "${REPORT_FILE}"
    clean_count=$(( clean_count + 1 ))
    continue
  fi

  echo "DIRTY_BEFORE | ${item_rel}" >> "${REPORT_FILE}"
  printf '%s\n' "${status_before}" | sed 's/^/  /' >> "${REPORT_FILE}"
  dirty_count=$(( dirty_count + 1 ))

  if [[ "${MODE}" == "apply" ]]; then
    git -C "${ROOT}" restore --source=HEAD --worktree -- "${item_rel}"
    git -C "${ROOT}" clean -fd -- "${item_rel}"

    status_after="$(current_status_block "${item_rel}")"
    if [[ -z "${status_after}" ]]; then
      echo "APPLIED_CLEAN | ${item_rel}" >> "${REPORT_FILE}"
      applied_clean_count=$(( applied_clean_count + 1 ))
    else
      echo "APPLIED_RESIDUAL | ${item_rel}" >> "${REPORT_FILE}"
      printf '%s\n' "${status_after}" | sed 's/^/  /' >> "${REPORT_FILE}"
      applied_residual_count=$(( applied_residual_count + 1 ))
    fi
  fi

  echo >> "${REPORT_FILE}"
done

cat > "${SUMMARY_FILE}" <<EOF
# Retrieval Execution Frozen Artifact Scrub

- Generated at: ${STAMP}
- Mode: ${MODE}
- Root: ${ROOT}

## Purpose

This script inspects tracked historical retrieval-execution artifact paths and
finds historical directories that became dirty after later regress/composition runs.

It explicitly protects:
- the tracked latest symlink path;
- the current latest target directory.

## Results

- tracked items scanned: ${tracked_count}
- latest symlink skipped: ${latest_symlink_skipped}
- latest target skipped: ${latest_target_skipped}
- clean historical tracked items: ${clean_count}
- dirty historical tracked items: ${dirty_count}
- applied clean after scrub: ${applied_clean_count}
- applied residual after scrub: ${applied_residual_count}

## Files

- Report: ${REPORT_FILE}
- Summary: ${SUMMARY_FILE}

## Apply behavior

When run in apply mode, the script:
- restores tracked files in dirty historical directories from git HEAD;
- removes untracked files inside those same directories;
- re-checks the same path after scrub and records whether it became clean.

The latest symlink path itself is never scrubbed here.
EOF

echo "SCRUB_OUTDIR=${OUTDIR}"
echo "REPORT_FILE=${REPORT_FILE}"
echo "SUMMARY_FILE=${SUMMARY_FILE}"
echo
sed -n '1,220p' "${SUMMARY_FILE}"
echo
echo "REPORT_PREVIEW_BEGIN"
sed -n '1,220p' "${REPORT_FILE}"
echo "REPORT_PREVIEW_END"