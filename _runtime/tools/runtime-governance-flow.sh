#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/agent/agents"
TOOLS_DIR="$REPO_ROOT/_runtime/tools"

SYNC_TOOL="$TOOLS_DIR/sync-protected-runtime.sh"
MANIFEST_TOOL="$TOOLS_DIR/build-runtime-manifest.py"
REGISTRY_TOOL="$TOOLS_DIR/build-runtime-registry.py"
GOV_STATUS="$TOOLS_DIR/runtime-governance-status.sh"
WORKFLOW_DOC="$REPO_ROOT/_runtime/RUNTIME_SYNC_WORKFLOW.md"

usage() {
  cat <<'EOF'
Usage:
  runtime-governance-flow.sh status
  runtime-governance-flow.sh refresh

Modes:
  status   Run only the governance status snapshot.
  refresh  Refresh canonical runtime state, rebuild manifest, rebuild registry, then run governance status snapshot.
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

MODE="${1:-status}"

git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "repo not available: $REPO_ROOT"
[ -f "$WORKFLOW_DOC" ] || die "missing workflow doc: $WORKFLOW_DOC"
[ -f "$SYNC_TOOL" ] || die "missing sync tool: $SYNC_TOOL"
[ -f "$MANIFEST_TOOL" ] || die "missing manifest tool: $MANIFEST_TOOL"
[ -f "$REGISTRY_TOOL" ] || die "missing registry tool: $REGISTRY_TOOL"
[ -f "$GOV_STATUS" ] || die "missing governance status tool: $GOV_STATUS"

case "$MODE" in
  status|refresh) ;;
  -h|--help|help)
    usage
    exit 0
    ;;
  *)
    usage >&2
    die "unsupported mode: $MODE"
    ;;
esac

echo "== runtime governance flow =="
echo "repo        : $REPO_ROOT"
echo "workflow    : $WORKFLOW_DOC"
echo "sync_tool   : $SYNC_TOOL"
echo "manifest    : $MANIFEST_TOOL"
echo "registry    : $REGISTRY_TOOL"
echo "gov_status  : $GOV_STATUS"
echo "mode        : $MODE"
echo

if [ "$MODE" = "refresh" ]; then
  echo "NOTE: run file-specific validation before refresh mode."
  echo "NOTE: refresh mode does not replace bash -n, py_compile, smoke, or regression."
  echo "NOTE: refresh mode is governance-oriented, not commit-readiness-oriented."
  echo

  echo "== step 1/4: sync protected runtime =="
  set +e
  bash "$SYNC_TOOL"
  sync_rc=$?
  set -e

  if [ "$sync_rc" -ne 0 ]; then
    echo
    echo "GOVERNANCE_FLOW=BLOCK"
    echo "MODE=refresh"
    echo "BLOCKER=sync_failed"
    echo "NEXT=fix_sync_then_rerun_refresh"
    exit "$sync_rc"
  fi

  echo
  echo "== step 2/4: build runtime manifest =="
  set +e
  python3 "$MANIFEST_TOOL"
  manifest_rc=$?
  set -e

  if [ "$manifest_rc" -ne 0 ]; then
    echo
    echo "GOVERNANCE_FLOW=BLOCK"
    echo "MODE=refresh"
    echo "BLOCKER=manifest_failed"
    echo "NEXT=fix_manifest_or_runtime_state_then_rerun_refresh"
    exit "$manifest_rc"
  fi

  echo
  echo "== step 3/4: build runtime registry =="
  set +e
  python3 "$REGISTRY_TOOL"
  registry_rc=$?
  set -e

  if [ "$registry_rc" -ne 0 ]; then
    echo
    echo "GOVERNANCE_FLOW=BLOCK"
    echo "MODE=refresh"
    echo "BLOCKER=registry_failed"
    echo "NEXT=fix_registry_or_runtime_layer_then_rerun_refresh"
    exit "$registry_rc"
  fi

  echo
  echo "== step 4/4: governance status snapshot =="
else
  echo "== step 1/1: governance status snapshot =="
fi

set +e
bash "$GOV_STATUS"
gov_rc=$?
set -e

echo
if [ "$gov_rc" -eq 0 ]; then
  echo "GOVERNANCE_FLOW=OK"
  echo "MODE=$MODE"
  if [ "$MODE" = "refresh" ]; then
    echo "NEXT=review_git_state_then_commit_if_needed"
  else
    echo "NEXT=continue_or_make_changes"
  fi
  exit 0
fi

echo "GOVERNANCE_FLOW=BLOCK"
echo "MODE=$MODE"
if [ "$MODE" = "refresh" ]; then
  echo "NEXT=fix_sync_manifest_registry_or_governance_blockers_then_rerun_refresh"
else
  echo "NEXT=fix_governance_blockers_then_rerun_status"
fi
exit "$gov_rc"