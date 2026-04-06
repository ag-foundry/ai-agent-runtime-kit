#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/home/agent/agents/core/runtime/retrieval-execution"
BIN_DIR="/home/agent/bin"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="/home/agent/bin/retrieval-execution-deploy-backup-${STAMP}"
MODE="${1:---runtime-smoke}"

FILES=(
  "retrieval-execution-admin"
  "run-retrieval-execution"
  "run-retrieval-execution-default"
  "run-retrieval-execution-v1-canonical-v2"
  "run-retrieval-execution-v1-composed-v2"
  "run-retrieval-execution-v1"
)

run_status_smoke() {
  echo
  echo "STATUS_SMOKE_BEGIN"
  /home/agent/bin/run-retrieval-execution status
  echo "STATUS_SMOKE_END"

  echo
  echo "ADMIN_STATUS_SMOKE_BEGIN"
  /home/agent/bin/retrieval-execution-admin status
  echo "ADMIN_STATUS_SMOKE_END"
}

run_full_smoke() {
  run_status_smoke

  echo
  echo "PUBLIC_RUN_SMOKE_BEGIN"
  /home/agent/bin/run-retrieval-execution
  echo "PUBLIC_RUN_SMOKE_END"

  echo
  echo "REGRESS_SMOKE_BEGIN"
  /home/agent/bin/run-retrieval-execution regress --topic core
  echo "REGRESS_SMOKE_END"

  echo
  echo "FULL_REGRESS_SMOKE_BEGIN"
  /home/agent/bin/run-retrieval-execution full-regress --topic core
  echo "FULL_REGRESS_SMOKE_END"
}

echo "DEPLOY_MODE=${MODE}"
echo "REPO_DIR=${REPO_DIR}"
echo "BIN_DIR=${BIN_DIR}"

mkdir -p "${BACKUP_DIR}"

for file in "${FILES[@]}"; do
  src="${REPO_DIR}/${file}"
  dst="${BIN_DIR}/${file}"

  if [[ ! -f "${src}" ]]; then
    echo "ERROR: missing source file: ${src}" >&2
    exit 1
  fi

  if [[ ! -s "${src}" ]]; then
    echo "ERROR: source file is empty: ${src}" >&2
    exit 1
  fi

  if [[ -e "${dst}" ]]; then
    cp -a "${dst}" "${BACKUP_DIR}/${file}"
  fi

  install -m 755 "${src}" "${dst}"
done

echo
echo "SHA256_VERIFY_BEGIN"
for file in "${FILES[@]}"; do
  src="${REPO_DIR}/${file}"
  dst="${BIN_DIR}/${file}"

  src_hash="$(sha256sum "${src}" | awk '{print $1}')"
  dst_hash="$(sha256sum "${dst}" | awk '{print $1}')"

  echo "${file}"
  echo "  repo=${src_hash}"
  echo "  bin =${dst_hash}"

  if [[ "${src_hash}" != "${dst_hash}" ]]; then
    echo "ERROR: hash mismatch after deploy: ${file}" >&2
    exit 1
  fi
done
echo "SHA256_VERIFY_END"

case "${MODE}" in
  --runtime-smoke|--status-smoke)
    run_status_smoke
    ;;
  --full-smoke)
    run_full_smoke
    ;;
  *)
    echo "ERROR: unknown deploy mode: ${MODE}" >&2
    echo "Use: --runtime-smoke | --status-smoke | --full-smoke" >&2
    exit 1
    ;;
esac

echo
echo "DEPLOY_STATUS=ok"
echo "BACKUP_DIR=${BACKUP_DIR}"