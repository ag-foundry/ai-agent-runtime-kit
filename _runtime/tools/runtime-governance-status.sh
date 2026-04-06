#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/agent/agents"
TOOLS_DIR="$REPO_ROOT/_runtime/tools"

STATUS_TOOL="$TOOLS_DIR/status-protected-runtime.sh"
MANIFEST_FILE="$REPO_ROOT/_runtime/canonical/meta/runtime-manifest.json"
REGISTRY_FILE="$REPO_ROOT/_runtime/runtime-registry.json"
WORKFLOW_DOC="$REPO_ROOT/_runtime/RUNTIME_SYNC_WORKFLOW.md"
RUNTIME_README="$REPO_ROOT/_runtime/README.md"
TOOLS_README="$REPO_ROOT/_runtime/tools/README.md"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "repo not available: $REPO_ROOT"
[ -f "$STATUS_TOOL" ] || die "missing status tool: $STATUS_TOOL"

status_tmp="$(mktemp)"
manifest_tmp="$(mktemp)"
registry_tmp="$(mktemp)"
trap 'rm -f "$status_tmp" "$manifest_tmp" "$registry_tmp"' EXIT

echo "== runtime governance status =="
echo "repo          : $REPO_ROOT"
echo "status_tool   : $STATUS_TOOL"
echo "manifest_file : $MANIFEST_FILE"
echo "registry_file : $REGISTRY_FILE"
echo

echo "== protected runtime status =="
set +e
bash "$STATUS_TOOL" | tee "$status_tmp"
status_rc=$?
set -e

protected_status="$(awk -F= '/^STATUS=/{print $2}' "$status_tmp" | tail -n1)"
if [ -z "$protected_status" ]; then
  protected_status="UNKNOWN"
fi

manifest_exists="NO"
manifest_parse_ok="NO"
manifest_in_sync="NO"
manifest_schema=""
manifest_generated_at_utc=""
manifest_protected_file_count=""

if [ -f "$MANIFEST_FILE" ]; then
  manifest_exists="YES"

  set +e
  python3 - "$MANIFEST_FILE" >"$manifest_tmp" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
summary = data.get("summary") or {}

print("manifest_parse_ok=YES")
print(f"manifest_schema={data.get('schema_version', '')}")
print(f"manifest_generated_at_utc={data.get('generated_at_utc', '')}")
print(f"manifest_protected_file_count={summary.get('protected_file_count', '')}")
print(f"manifest_in_sync={'YES' if bool(summary.get('in_sync')) else 'NO'}")
PY
  manifest_rc=$?
  set -e

  if [ "$manifest_rc" -eq 0 ]; then
    while IFS='=' read -r key value; do
      case "$key" in
        manifest_parse_ok) manifest_parse_ok="$value" ;;
        manifest_schema) manifest_schema="$value" ;;
        manifest_generated_at_utc) manifest_generated_at_utc="$value" ;;
        manifest_protected_file_count) manifest_protected_file_count="$value" ;;
        manifest_in_sync) manifest_in_sync="$value" ;;
      esac
    done < "$manifest_tmp"
  fi
fi

registry_exists="NO"
registry_parse_ok="NO"
registry_schema=""
registry_generated_at_utc=""
registry_manifest_generated_at_utc=""
registry_required_docs_present="NO"
registry_required_tools_present="NO"
registry_executable_tools_ok="NO"
registry_manifest_healthy="NO"
registry_registry_healthy="NO"

if [ -f "$REGISTRY_FILE" ]; then
  registry_exists="YES"

  set +e
  python3 - "$REGISTRY_FILE" >"$registry_tmp" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
summary = data.get("governance_summary") or {}
manifest = data.get("manifest_summary") or {}

print("registry_parse_ok=YES")
print(f"registry_schema={data.get('schema_version', '')}")
print(f"registry_generated_at_utc={data.get('generated_at_utc', '')}")
print(f"registry_manifest_generated_at_utc={manifest.get('generated_at_utc', '')}")
print(f"registry_required_docs_present={'YES' if bool(summary.get('required_docs_present')) else 'NO'}")
print(f"registry_required_tools_present={'YES' if bool(summary.get('required_tools_present')) else 'NO'}")
print(f"registry_executable_tools_ok={'YES' if bool(summary.get('executable_tools_ok')) else 'NO'}")
print(f"registry_manifest_healthy={'YES' if bool(summary.get('manifest_healthy')) else 'NO'}")
print(f"registry_registry_healthy={'YES' if bool(summary.get('registry_healthy')) else 'NO'}")
PY
  registry_rc=$?
  set -e

  if [ "$registry_rc" -eq 0 ]; then
    while IFS='=' read -r key value; do
      case "$key" in
        registry_parse_ok) registry_parse_ok="$value" ;;
        registry_schema) registry_schema="$value" ;;
        registry_generated_at_utc) registry_generated_at_utc="$value" ;;
        registry_manifest_generated_at_utc) registry_manifest_generated_at_utc="$value" ;;
        registry_required_docs_present) registry_required_docs_present="$value" ;;
        registry_required_tools_present) registry_required_tools_present="$value" ;;
        registry_executable_tools_ok) registry_executable_tools_ok="$value" ;;
        registry_manifest_healthy) registry_manifest_healthy="$value" ;;
        registry_registry_healthy) registry_registry_healthy="$value" ;;
      esac
    done < "$registry_tmp"
  fi
fi

workflow_doc_present="NO"
runtime_readme_present="NO"
tools_readme_present="NO"

[ -f "$WORKFLOW_DOC" ] && workflow_doc_present="YES"
[ -f "$RUNTIME_README" ] && runtime_readme_present="YES"
[ -f "$TOOLS_README" ] && tools_readme_present="YES"

required_docs_present="YES"
if [ "$workflow_doc_present" != "YES" ] || [ "$runtime_readme_present" != "YES" ] || [ "$tools_readme_present" != "YES" ]; then
  required_docs_present="NO"
fi

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

repo_clean="YES"
if [ "$change_count" -gt 0 ]; then
  repo_clean="NO"
fi

echo
echo "== manifest summary =="
echo "manifest_exists              : $manifest_exists"
echo "manifest_parse_ok            : $manifest_parse_ok"
echo "manifest_schema              : $manifest_schema"
echo "manifest_generated_at_utc    : $manifest_generated_at_utc"
echo "manifest_protected_file_count: $manifest_protected_file_count"
echo "manifest_in_sync             : $manifest_in_sync"

echo
echo "== registry summary =="
echo "registry_exists                  : $registry_exists"
echo "registry_parse_ok                : $registry_parse_ok"
echo "registry_schema                  : $registry_schema"
echo "registry_generated_at_utc        : $registry_generated_at_utc"
echo "registry_manifest_generated_at_utc: $registry_manifest_generated_at_utc"
echo "registry_required_docs_present   : $registry_required_docs_present"
echo "registry_required_tools_present  : $registry_required_tools_present"
echo "registry_executable_tools_ok     : $registry_executable_tools_ok"
echo "registry_manifest_healthy        : $registry_manifest_healthy"
echo "registry_registry_healthy        : $registry_registry_healthy"

echo
echo "== required docs =="
echo "workflow_doc_present  : $workflow_doc_present"
echo "runtime_readme_present: $runtime_readme_present"
echo "tools_readme_present  : $tools_readme_present"

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

protected_ok="NO"
if [ "$status_rc" -eq 0 ] && [ "$protected_status" = "IN_SYNC" ]; then
  protected_ok="YES"
fi

manifest_ok="NO"
if [ "$manifest_exists" = "YES" ] && [ "$manifest_parse_ok" = "YES" ] && [ "$manifest_in_sync" = "YES" ]; then
  manifest_ok="YES"
fi

registry_ok="NO"
if [ "$registry_exists" = "YES" ] && [ "$registry_parse_ok" = "YES" ] && [ "$registry_registry_healthy" = "YES" ]; then
  registry_ok="YES"
fi

echo
echo "== governance summary =="
echo "CHECK.protected_runtime_in_sync=$protected_ok"
echo "CHECK.manifest_present=$manifest_exists"
echo "CHECK.manifest_in_sync=$manifest_ok"
echo "CHECK.registry_present=$registry_exists"
echo "CHECK.registry_healthy=$registry_ok"
echo "CHECK.required_docs_present=$required_docs_present"
echo "CHECK.repo_clean=$repo_clean"

if [ "$protected_ok" != "YES" ] || [ "$manifest_ok" != "YES" ] || [ "$registry_ok" != "YES" ] || [ "$required_docs_present" != "YES" ]; then
  echo "GOVERNANCE_STATUS=BLOCK"
  echo "NEXT=fix_runtime_manifest_registry_or_docs_then_rerun_status"
  exit 3
fi

if [ "$repo_clean" != "YES" ]; then
  echo "GOVERNANCE_STATUS=REVIEW"
  echo "NEXT=review_git_state_then_commit_or_restore"
  exit 0
fi

echo "GOVERNANCE_STATUS=HEALTHY"
echo "NEXT=continue_or_make_changes"