#!/usr/bin/env bash
set -euo pipefail

export GIT_PAGER=cat
export PAGER=cat

ROOT="/home/agent/agents"
STAMP="$(date +%Y-%m-%d-%H%M%S)"
OUTDIR="${ROOT}/core/artifacts/maintenance/retrieval-execution-hygiene/${STAMP}"

mkdir -p "${OUTDIR}"

STATUS_FILE="${OUTDIR}/git-status-filtered.txt"
LATEST_FILE="${OUTDIR}/latest-links.txt"
DIRS_FILE="${OUTDIR}/artifact-directories.txt"
SUMMARY_FILE="${OUTDIR}/SUMMARY.md"

FILTER='^.. (core/artifacts/retrieval-execution|core/artifacts/retrieval-execution-canonical-regress|core/artifacts/retrieval-execution-canonical-full-regress|core/artifacts/answer-composition|core/artifacts/answer-composition-preview|core/artifacts/retrieval-answer-intent-audit|core/runtime/retrieval-execution)'

git -C "${ROOT}" --no-pager status --short | grep -E "${FILTER}" > "${STATUS_FILE}" || true

{
  echo "LINK core/artifacts/retrieval-execution/latest"
  if [[ -L "${ROOT}/core/artifacts/retrieval-execution/latest" ]]; then
    readlink -f "${ROOT}/core/artifacts/retrieval-execution/latest"
  else
    echo "missing"
  fi
  echo

  echo "LINK core/artifacts/retrieval-execution-canonical-regress/latest"
  if [[ -L "${ROOT}/core/artifacts/retrieval-execution-canonical-regress/latest" ]]; then
    readlink -f "${ROOT}/core/artifacts/retrieval-execution-canonical-regress/latest"
  else
    echo "missing"
  fi
  echo

  echo "LINK core/artifacts/retrieval-execution-canonical-full-regress/latest"
  if [[ -L "${ROOT}/core/artifacts/retrieval-execution-canonical-full-regress/latest" ]]; then
    readlink -f "${ROOT}/core/artifacts/retrieval-execution-canonical-full-regress/latest"
  else
    echo "missing"
  fi
  echo

  echo "LINK core/artifacts/answer-composition/latest"
  if [[ -L "${ROOT}/core/artifacts/answer-composition/latest" ]]; then
    readlink -f "${ROOT}/core/artifacts/answer-composition/latest"
  else
    echo "missing"
  fi
  echo

  echo "LINK core/artifacts/answer-composition-preview/latest"
  if [[ -L "${ROOT}/core/artifacts/answer-composition-preview/latest" ]]; then
    readlink -f "${ROOT}/core/artifacts/answer-composition-preview/latest"
  else
    echo "missing"
  fi
  echo

  echo "LINK core/artifacts/retrieval-answer-intent-audit/latest"
  if [[ -L "${ROOT}/core/artifacts/retrieval-answer-intent-audit/latest" ]]; then
    readlink -f "${ROOT}/core/artifacts/retrieval-answer-intent-audit/latest"
  else
    echo "missing"
  fi
  echo
} > "${LATEST_FILE}"

{
  echo "# retrieval-execution"
  find "${ROOT}/core/artifacts/retrieval-execution" -mindepth 1 -maxdepth 1 -type d | sort || true
  echo

  echo "# retrieval-execution-canonical-regress"
  find "${ROOT}/core/artifacts/retrieval-execution-canonical-regress" -mindepth 1 -maxdepth 1 -type d | sort || true
  echo

  echo "# retrieval-execution-canonical-full-regress"
  find "${ROOT}/core/artifacts/retrieval-execution-canonical-full-regress" -mindepth 1 -maxdepth 1 -type d | sort || true
  echo
} > "${DIRS_FILE}"

status_count="$(wc -l < "${STATUS_FILE}" | tr -d ' ')"
re_count="$(find "${ROOT}/core/artifacts/retrieval-execution" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
reg_count="$(find "${ROOT}/core/artifacts/retrieval-execution-canonical-regress" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
full_count="$(find "${ROOT}/core/artifacts/retrieval-execution-canonical-full-regress" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"

cat > "${SUMMARY_FILE}" <<EOF
# Retrieval Execution Artifact Hygiene Audit

- Generated at: ${STAMP}
- Root: ${ROOT}

## Summary

- Filtered git status entries: ${status_count}
- retrieval-execution directories: ${re_count}
- canonical-regress directories: ${reg_count}
- canonical-full-regress directories: ${full_count}

## Files

- Status: ${STATUS_FILE}
- Latest links: ${LATEST_FILE}
- Directory inventory: ${DIRS_FILE}

## Interpretation

This audit does not delete anything.

Its purpose is to show:

1. which retrieval-execution related paths are still dirty in git status;
2. which latest symlinks currently define the active artifact heads;
3. how many timestamped artifact directories have accumulated.

The next safe step is to design a retention / cleanup rule from this audit output,
instead of deleting historical artifacts blindly.
EOF

echo "AUDIT_OUTDIR=${OUTDIR}"
echo "SUMMARY_FILE=${SUMMARY_FILE}"
echo "STATUS_FILE=${STATUS_FILE}"
echo "LATEST_FILE=${LATEST_FILE}"
echo "DIRS_FILE=${DIRS_FILE}"
echo
sed -n '1,200p' "${SUMMARY_FILE}"