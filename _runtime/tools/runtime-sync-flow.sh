#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/agent/agents"
TOOLS_DIR="$REPO_ROOT/_runtime/tools"

SYNC_TOOL="$TOOLS_DIR/sync-protected-runtime.sh"
MANIFEST_TOOL="$TOOLS_DIR/build-runtime-manifest.py"
REGISTRY_TOOL="$TOOLS_DIR/build-runtime-registry.py"
READINESS_TOOL="$TOOLS_DIR/runtime-commit-readiness.sh"
WORKFLOW_DOC="$REPO_ROOT/_runtime/RUNTIME_SYNC_WORKFLOW.md"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "repo not available: $REPO_ROOT"
[ -f "$WORKFLOW_DOC" ] || die "missing workflow doc: $WORKFLOW_DOC"
[ -f "$SYNC_TOOL" ] || die "missing sync tool: $SYNC_TOOL"
[ -f "$MANIFEST_TOOL" ] || die "missing manifest tool: $MANIFEST_TOOL"
[ -f "$REGISTRY_TOOL" ] || die "missing registry tool: $REGISTRY_TOOL"
[ -f "$READINESS_TOOL" ] || die "missing readiness tool: $READINESS_TOOL"

echo "== runtime sync flow =="
echo "repo      : $REPO_ROOT"
echo "workflow  : $WORKFLOW_DOC"
echo "sync_tool : $SYNC_TOOL"
echo "manifest  : $MANIFEST_TOOL"
echo "registry  : $REGISTRY_TOOL"
echo "readiness : $READINESS_TOOL"
echo
echo "NOTE: run file-specific validation before this flow."
echo "NOTE: this flow does not replace bash -n, py_compile, smoke, or regression."
echo "NOTE: manifest and registry builders are idempotent and should not create git churn without real state change."
echo "NOTE: readiness helper already includes the protected runtime status check."
echo

echo "== step 1/4: sync protected runtime =="
bash "$SYNC_TOOL"

echo
echo "== step 2/4: build runtime manifest =="
set +e
python3 "$MANIFEST_TOOL"
manifest_rc=$?
set -e

if [ "$manifest_rc" -ne 0 ]; then
  echo
  echo "FLOW_RESULT=BLOCK"
  echo "BLOCKER=manifest_build_or_sync_state_failed"
  echo "NEXT=fix_manifest_or_runtime_sync_then_rerun_flow"
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
  echo "FLOW_RESULT=BLOCK"
  echo "BLOCKER=registry_build_or_runtime_layer_failed"
  echo "NEXT=fix_registry_or_runtime_layer_then_rerun_flow"
  exit "$registry_rc"
fi

echo
echo "== step 4/4: readiness check =="
set +e
bash "$READINESS_TOOL"
readiness_rc=$?
set -e

echo
if [ "$readiness_rc" -eq 0 ]; then
  echo "FLOW_RESULT=OK"
  echo "NEXT=review_git_then_commit_push"
  exit 0
fi

echo "FLOW_RESULT=BLOCK"
echo "NEXT=fix_blockers_then_rerun_flow"
exit "$readiness_rc"