#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/agent/agents"
WORKFLOW_DOC="$REPO_ROOT/_runtime/RUNTIME_SYNC_WORKFLOW.md"
STATUS_TOOL="$REPO_ROOT/_runtime/tools/status-protected-runtime.sh"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "repo not available: $REPO_ROOT"
[ -f "$WORKFLOW_DOC" ] || die "missing workflow doc: $WORKFLOW_DOC"
[ -f "$STATUS_TOOL" ] || die "missing status tool: $STATUS_TOOL"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

echo "== runtime commit readiness =="
echo "repo        : $REPO_ROOT"
echo "workflow    : $WORKFLOW_DOC"
echo "status_tool : $STATUS_TOOL"
echo

if ! bash "$STATUS_TOOL" | tee "$tmp"; then
  echo
  echo "CHECK.canonical_in_sync=NO"
  echo "CHECK.repo_has_changes=UNKNOWN"
  echo "CHECK.untracked_review_required=UNKNOWN"
  echo "COMMIT_READINESS=BLOCK"
  echo "BLOCKER=status_tool_failed"
  exit 2
fi

sync_status="$(awk -F= '/^STATUS=/{print $2}' "$tmp" | tail -n1)"

status_text="$(git -C "$REPO_ROOT" status --short || true)"
change_count=0
tracked_count=0
untracked_count=0

if [ -n "$status_text" ]; then
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    change_count=$((change_count + 1))
    case "$line" in
      '?? '*) untracked_count=$((untracked_count + 1)) ;;
      *) tracked_count=$((tracked_count + 1)) ;;
    esac
  done <<< "$status_text"
fi

echo
echo "== git status summary =="
echo "changes_total   : $change_count"
echo "tracked_changes : $tracked_count"
echo "untracked_files : $untracked_count"
if [ -n "$status_text" ]; then
  printf '%s\n' "$status_text"
else
  echo "working tree clean"
fi

echo
echo "== checklist snapshot =="

if [ "$sync_status" = "IN_SYNC" ]; then
  echo "CHECK.canonical_in_sync=YES"
else
  echo "CHECK.canonical_in_sync=NO"
fi

if [ "$change_count" -gt 0 ]; then
  echo "CHECK.repo_has_changes=YES"
else
  echo "CHECK.repo_has_changes=NO"
fi

if [ "$untracked_count" -gt 0 ]; then
  echo "CHECK.untracked_review_required=YES"
else
  echo "CHECK.untracked_review_required=NO"
fi

echo "WORKFLOW_DOC=$WORKFLOW_DOC"

if [ "$sync_status" != "IN_SYNC" ]; then
  echo "COMMIT_READINESS=BLOCK"
  echo "BLOCKER=runtime_not_in_sync"
  exit 3
fi

if [ "$change_count" -eq 0 ]; then
  echo "COMMIT_READINESS=BLOCK"
  echo "BLOCKER=no_repo_changes"
  exit 4
fi

if [ "$untracked_count" -gt 0 ]; then
  echo "COMMIT_READINESS=REVIEW"
  echo "NEXT=review_untracked_then_git_add_commit_push"
  exit 0
fi

echo "COMMIT_READINESS=READY"
echo "NEXT=git_add_commit_push"