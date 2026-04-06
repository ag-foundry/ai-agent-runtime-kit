#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/agent/agents"
RUNTIME_DIR="${ROOT}/core/runtime/retrieval-execution"
DEPLOY_SCRIPT="${RUNTIME_DIR}/deploy-retrieval-execution-runtime.sh"
STAMP="$(date +%Y-%m-%d-%H%M%S)"
NOTE="${*:-repo-backed runtime sync}"
COMMIT_MESSAGE="Checkpoint retrieval-execution runtime: ${NOTE} (${STAMP})"

echo "PUBLISH_ROOT=${ROOT}"
echo "RUNTIME_DIR=${RUNTIME_DIR}"
echo "DEPLOY_SCRIPT=${DEPLOY_SCRIPT}"
echo "NOTE=${NOTE}"

if [[ ! -x "${DEPLOY_SCRIPT}" ]]; then
  echo "ERROR: deploy script is missing or not executable: ${DEPLOY_SCRIPT}" >&2
  exit 1
fi

if [[ ! -d "${ROOT}/.git" ]]; then
  echo "ERROR: git repo not found at ${ROOT}" >&2
  exit 1
fi

echo
echo "STEP=deploy_runtime_smoke"
"${DEPLOY_SCRIPT}" --runtime-smoke

echo
echo "STEP=git_add_runtime_dir"
git -C "${ROOT}" add core/runtime/retrieval-execution

echo
echo "STAGED_FILES_BEGIN"
git -C "${ROOT}" diff --cached --name-only
echo "STAGED_FILES_END"

if git -C "${ROOT}" diff --cached --quiet; then
  echo
  echo "PUBLISH_STATUS=no_changes"
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
echo "PUBLISH_STATUS=ok"