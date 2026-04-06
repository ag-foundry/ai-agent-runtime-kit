#!/usr/bin/env bash
set -euo pipefail

export GIT_PAGER=cat
export PAGER=cat

ROOT="/home/agent/agents"
RUNTIME_DIR="${ROOT}/core/runtime/retrieval-execution"
DEPLOY_SCRIPT="${RUNTIME_DIR}/deploy-retrieval-execution-runtime.sh"
FROZEN_SCRUB_SCRIPT="${RUNTIME_DIR}/scrub-retrieval-execution-frozen-artifacts.sh"
STAMP="$(date +%Y-%m-%d-%H%M%S)"
NOTE="${*:-retrieval-execution checkpoint}"
COMMIT_MESSAGE="Checkpoint retrieval-execution package: ${NOTE} (${STAMP})"

stage_if_exists() {
  local rel="$1"
  if [[ -e "${ROOT}/${rel}" || -L "${ROOT}/${rel}" ]]; then
    git -C "${ROOT}" add -f -- "${rel}"
    echo "STAGED=${rel}"
  else
    echo "SKIP_MISSING=${rel}"
  fi
}

stage_latest_bundle() {
  local rel="$1"
  local abs="${ROOT}/${rel}"

  if [[ -L "${abs}" ]]; then
    stage_if_exists "${rel}"
    local target_abs
    local target_rel
    target_abs="$(readlink -f "${abs}")"
    target_rel="$(realpath --relative-to="${ROOT}" "${target_abs}")"
    stage_if_exists "${target_rel}"
    return 0
  fi

  if [[ -e "${abs}" ]]; then
    stage_if_exists "${rel}"
    return 0
  fi

  echo "SKIP_MISSING=${rel}"
}

echo "CHECKPOINT_ROOT=${ROOT}"
echo "RUNTIME_DIR=${RUNTIME_DIR}"
echo "DEPLOY_SCRIPT=${DEPLOY_SCRIPT}"
echo "FROZEN_SCRUB_SCRIPT=${FROZEN_SCRUB_SCRIPT}"
echo "NOTE=${NOTE}"

if [[ ! -x "${DEPLOY_SCRIPT}" ]]; then
  echo "ERROR: deploy script is missing or not executable: ${DEPLOY_SCRIPT}" >&2
  exit 1
fi

if [[ ! -x "${FROZEN_SCRUB_SCRIPT}" ]]; then
  echo "ERROR: frozen scrub script is missing or not executable: ${FROZEN_SCRUB_SCRIPT}" >&2
  exit 1
fi

if [[ ! -d "${ROOT}/.git" ]]; then
  echo "ERROR: git repo not found at ${ROOT}" >&2
  exit 1
fi

echo
echo "STEP=deploy_full_smoke"
"${DEPLOY_SCRIPT}" --full-smoke

echo
echo "STEP=frozen_scrub_apply"
"${FROZEN_SCRUB_SCRIPT}" apply

echo
echo "STEP=git_add_curated_checkpoint"

stage_if_exists "core/runtime/retrieval-execution"
stage_if_exists "core/artifacts/.gitignore"

stage_if_exists "core/artifacts/architecture/latest-answer-composition-quality-v2-contract.md"
stage_if_exists "core/artifacts/architecture/latest-retrieval-execution-canonical-v2-checkpoint.md"
stage_if_exists "core/artifacts/architecture/latest-retrieval-execution-canonical-v2-freeze.md"
stage_if_exists "core/artifacts/architecture/latest-retrieval-execution-command-surface-sync.md"
stage_if_exists "core/artifacts/architecture/latest-retrieval-execution-default-routing-freeze.md"

stage_if_exists "core/artifacts/answer-composition"
stage_if_exists "core/artifacts/answer-composition-preview"
stage_if_exists "core/artifacts/retrieval-answer-intent-audit"
stage_if_exists "core/artifacts/maintenance"

stage_latest_bundle "core/artifacts/retrieval-execution/latest"
stage_latest_bundle "core/artifacts/retrieval-execution-canonical-regress/latest"
stage_latest_bundle "core/artifacts/retrieval-execution-canonical-full-regress/latest"

echo
echo "STAGED_FILES_BEGIN"
git -C "${ROOT}" --no-pager diff --cached --name-only
echo "STAGED_FILES_END"

if git -C "${ROOT}" diff --cached --quiet; then
  echo
  echo "CHECKPOINT_STATUS=no_changes"
  exit 0
fi

echo
echo "STEP=git_commit"
git -C "${ROOT}" commit -m "${COMMIT_MESSAGE}"

echo
echo "STEP=git_push"
git -C "${ROOT}" push origin main

echo
echo "LAST_COMMIT_BEGIN"
git -C "${ROOT}" --no-pager log --oneline -1
echo "LAST_COMMIT_END"

echo
echo "WORKTREE_STATUS_BEGIN"
git -C "${ROOT}" --no-pager status --short
echo "WORKTREE_STATUS_END"

echo
echo "CHECKPOINT_STATUS=ok"