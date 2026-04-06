#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/agent/agents"
OUTDIR="$ROOT/core/artifacts/audit/$(date +%Y-%m-%d-%H%M%S)-repo-overview"
REPORT="$OUTDIR/repo_audit.txt"

mkdir -p "$OUTDIR"

section() {
  echo
  echo "============================================================"
  echo "$1"
  echo "============================================================"
}

{
  section "REPO AUDIT OVERVIEW"
  echo "generated_at: $(date -Is)"
  echo "root: $ROOT"

  section "GIT BASICS"
  cd "$ROOT"
  echo "pwd:"
  pwd
  echo
  echo "remote:"
  git remote -v
  echo
  echo "branch:"
  git branch --show-current
  echo
  echo "status:"
  git status -sb
  echo
  echo "ahead/behind vs origin:"
  git rev-list --left-right --count HEAD...origin/main 2>/dev/null || true
  echo
  echo "last commits:"
  git log --oneline --decorate --graph -12

  section "TOP-LEVEL CONTENT"
  find "$ROOT" -maxdepth 2 -mindepth 1 -type d | sort

  section "TOPIC STRUCTURE CHECK"
  for topic in core audit-smoke; do
    echo "--- topic: $topic ---"
    for rel in \
      "README.md" \
      "AGENTS.md" \
      "LOG.md" \
      "TODO.md" \
      "memory/context.md" \
      "memory/index.md" \
      "memory/facts.md" \
      "memory/refs.md" \
      "memory/lessons.md"
    do
      if [[ -e "$ROOT/$topic/$rel" ]]; then
        echo "OK   $topic/$rel"
      else
        echo "MISS $topic/$rel"
      fi
    done
    echo
  done

  section "SHARED CANON FILES"
  for rel in \
    "_shared/AGENTS.md" \
    "_shared/README.md" \
    "_shared/SECURITY.md" \
    "_shared/NEWS.md" \
    "_shared/memory/index.md"
  do
    if [[ -e "$ROOT/$rel" ]]; then
      echo "OK   $rel"
    else
      echo "MISS $rel"
    fi
  done

  section "KEY RUNTIME FILES"
  for f in \
    "/home/agent/bin/project-research-run" \
    "/home/agent/bin/project-research-run.inner-step17-real-fetch-extraction" \
    "/home/agent/bin/validate-project-research-run" \
    "/home/agent/bin/project-research-eval" \
    "/home/agent/bin/project-research-regress" \
    "/home/agent/bin/project-research-regress-full"
  do
    if [[ -e "$f" ]]; then
      echo "OK   $f"
      ls -l "$f"
    else
      echo "MISS $f"
    fi
  done

  section "SHELL SYNTAX CHECK"
  for f in \
    "/home/agent/bin/project-research-run" \
    "/home/agent/bin/project-research-run.inner-step17-real-fetch-extraction" \
    "/home/agent/bin/validate-project-research-run" \
    "/home/agent/bin/project-research-eval" \
    "/home/agent/bin/project-research-regress" \
    "/home/agent/bin/project-research-regress-full"
  do
    if [[ -e "$f" ]]; then
      if bash -n "$f" >/dev/null 2>&1; then
        echo "OK   bash -n $f"
      else
        echo "FAIL bash -n $f"
      fi
    fi
  done

  section "PLAN-ANCHOR MARKERS IN RUNNER"
  grep -nE \
    'memory_first|PROJECT_RESEARCH_SEARCH_BACKEND|PROJECT_RESEARCH_EXECUTION_MODE|live_attempts|all_queries_zero_results|after retry|repo_context|retrieval_strategy' \
    /home/agent/bin/project-research-run.inner-step17-real-fetch-extraction || true

  section "LATEST ARTIFACT SUMMARY"
  python3 - <<'PY'
import json
from pathlib import Path

topics = ["core", "audit-smoke"]

for topic in topics:
    root = Path("/home/agent/agents") / topic / "artifacts" / "research"
    latest = root / "latest"
    print(f"\n--- topic: {topic} ---")
    print("latest_exists =", latest.exists() or latest.is_symlink())
    if latest.is_symlink():
        print("latest_target =", latest.resolve(strict=False))
    elif latest.exists():
        print("latest_target =", latest)

    dirs = sorted([p for p in root.iterdir() if p.is_dir() and p.name != "latest"], key=lambda p: p.name)
    print("recent_dirs =")
    for p in dirs[-5:]:
        print(" ", p.name)

    if not latest.exists():
        continue

    ctx_path = latest / "context.json"
    man_path = latest / "run_manifest.json"
    qual_path = latest / "quality_report.json"
    src_path = latest / "sources.json"
    find_path = latest / "findings.jsonl"
    prov_path = latest / "provenance.json"

    if not ctx_path.exists():
        print("context.json missing")
        continue

    ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
    esc = ctx.get("external_search_config") or {}
    print("mode =", ctx.get("mode"))
    print("search_backend =", ctx.get("search_backend"))
    print("retrieval_strategy =", ctx.get("retrieval_strategy"))
    print("retrieved_candidates_count =", esc.get("retrieved_candidates_count"))
    print("selected_external_sources_count =", esc.get("selected_external_sources_count"))
    print("live_attempts =", len(esc.get("live_attempts") or []))

    if man_path.exists():
        man = json.loads(man_path.read_text(encoding="utf-8"))
        print("runner_version =", man.get("runner_version"))
        print("execution_mode =", man.get("execution_mode"))

    if qual_path.exists():
        qual = json.loads(qual_path.read_text(encoding="utf-8"))
        print("quality_status =", qual.get("status"))
        print("passed_gates =", qual.get("passed_gates"))

    if src_path.exists():
        obj = json.loads(src_path.read_text(encoding="utf-8"))
        if isinstance(obj, list):
            sources = obj
        elif isinstance(obj, dict):
            sources = obj.get("sources") or []
        else:
            sources = []
        print("sources_count =", len(sources))

    if find_path.exists():
        findings = [x for x in find_path.read_text(encoding="utf-8").splitlines() if x.strip()]
        print("findings_count =", len(findings))

    if prov_path.exists():
        prov = json.loads(prov_path.read_text(encoding="utf-8"))
        if isinstance(prov, dict):
            refs = prov.get("references") or prov.get("provenance") or []
            try:
                print("provenance_refs_count =", len(refs))
            except Exception:
                print("provenance_refs_count = unknown")
PY

  section "RECENT CORE ARTIFACTS"
  python3 - <<'PY'
import json
from pathlib import Path

root = Path('/home/agent/agents/core/artifacts/research')
dirs = sorted([p for p in root.iterdir() if p.is_dir() and p.name != 'latest'], key=lambda p: p.name)[-8:]

for base in dirs:
    ctx_path = base / 'context.json'
    if not ctx_path.exists():
        continue
    ctx = json.loads(ctx_path.read_text(encoding='utf-8'))
    esc = ctx.get('external_search_config') or {}
    la = esc.get('live_attempts') or []
    print(base.name)
    print('  backend =', esc.get('backend'))
    print('  retrieved =', esc.get('retrieved_candidates_count'))
    print('  selected =', esc.get('selected_external_sources_count'))
    print('  live_attempts =', len(la))
    for row in la:
        print(
            '    attempt=', row.get('attempt'),
            'retrieved=', row.get('retrieved_candidates_count'),
            'selected=', row.get('selected_external_sources_count'),
            'all_zero=', row.get('all_queries_zero_results'),
        )
PY

  section "TODO OPEN ITEMS"
  for f in "$ROOT/core/TODO.md" "$ROOT/audit-smoke/TODO.md"; do
    echo "--- $f ---"
    if [[ -f "$f" ]]; then
      grep -nE '^\s*[-*]\s+\[ \]|^\s*TODO|^\s*Next|^\s*#' "$f" || true
    else
      echo "missing"
    fi
    echo
  done

  section "LOG TAILS"
  for f in "$ROOT/core/LOG.md" "$ROOT/audit-smoke/LOG.md"; do
    echo "--- tail: $f ---"
    if [[ -f "$f" ]]; then
      tail -n 40 "$f"
    else
      echo "missing"
    fi
    echo
  done

  section "MEMORY FILE HEADLINES"
  for f in \
    "$ROOT/core/memory/context.md" \
    "$ROOT/core/memory/index.md" \
    "$ROOT/core/memory/facts.md" \
    "$ROOT/core/memory/lessons.md"
  do
    echo "--- $f ---"
    if [[ -f "$f" ]]; then
      sed -n '1,80p' "$f"
    else
      echo "missing"
    fi
    echo
  done

  section "UNTRACKED FILES"
  git ls-files --others --exclude-standard | sed -n '1,200p'

  section "SUMMARY HINTS"
  echo "1) If git status is clean and latest artifacts are healthy, repo state is coherent."
  echo "2) If TODO still shows unfinished items, that is remaining work."
  echo "3) If plan-anchor markers exist, drift from the core architecture is less likely."
  echo "4) Human review still needed for: roadmap alignment, priority drift, and next-step choice."

} > "$REPORT"

echo "REPORT=$REPORT"
echo
echo "Preview:"
sed -n '1,260p' "$REPORT"