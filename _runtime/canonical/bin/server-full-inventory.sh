#!/usr/bin/env bash
set -euo pipefail

ROOT_AGENTS="/home/agent/agents"
ROOT_BIN="/home/agent/bin"
OUTDIR="$ROOT_AGENTS/core/artifacts/inventory/$(date +%Y-%m-%d-%H%M%S)-server-full-inventory"

mkdir -p "$OUTDIR"

section() {
  echo
  echo "============================================================"
  echo "$1"
  echo "============================================================"
}

section_file() {
  local title="$1"
  local file="$2"
  {
    echo
    echo "============================================================"
    echo "$title"
    echo "============================================================"
    cat "$file"
    echo
  } >> "$OUTDIR/REPORT.txt"
}

echo "OUTDIR=$OUTDIR"

find "$ROOT_BIN" -maxdepth 1 -type f | sort > "$OUTDIR/bin-files.txt"
find "$ROOT_BIN" -maxdepth 1 -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS | %10s | %p\n' | sort > "$OUTDIR/bin-files-detailed.txt"

find "$ROOT_AGENTS" -maxdepth 3 -type d | sort > "$OUTDIR/agents-dirs.txt"
find "$ROOT_AGENTS" -maxdepth 4 -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS | %10s | %p\n' | sort > "$OUTDIR/agents-files-detailed.txt"

find "$ROOT_AGENTS" -type f \( \
  -name '*.bak' -o \
  -name '*.bak.*' -o \
  -name '*.tmp' -o \
  -name '*.old' -o \
  -name '*~' -o \
  -name '*.orig' -o \
  -name '*.rej' \
\) | sort > "$OUTDIR/backup-temp-files.txt"

find "$ROOT_AGENTS" -type d \( \
  -name '__pycache__' -o \
  -name '.pytest_cache' -o \
  -name '.mypy_cache' -o \
  -name '.ruff_cache' \
\) | sort > "$OUTDIR/cache-dirs.txt"

find "$ROOT_AGENTS" -type f -size +1M -printf '%10s | %p\n' | sort -nr > "$OUTDIR/large-files.txt"

git -C "$ROOT_AGENTS" status -sb > "$OUTDIR/git-status.txt"
git -C "$ROOT_AGENTS" ls-files --others --exclude-standard > "$OUTDIR/git-untracked.txt"
git -C "$ROOT_AGENTS" log --oneline --decorate -20 > "$OUTDIR/git-log.txt"

python3 - <<'PY' > "$OUTDIR/classified-summary.txt"
from pathlib import Path
from collections import Counter

roots = [Path('/home/agent/bin'), Path('/home/agent/agents')]
counter = Counter()

def classify(path: Path) -> str:
    s = str(path)
    name = path.name.lower()

    if '/artifacts/' in s:
        return 'artifact'
    if '/runs/' in s:
        return 'run-trace'
    if '/memory/' in s:
        return 'memory'
    if '/DECISIONS/' in s:
        return 'decision'
    if s.startswith('/home/agent/bin/'):
        return 'runtime-bin'
    if name.endswith(('.bak', '.tmp', '.old', '.orig', '.rej')) or '.bak.' in name:
        return 'backup-temp'
    if name in {'readme.md', 'agents.md', 'todo.md', 'log.md'}:
        return 'topic-control'
    if name.endswith(('.json', '.yaml', '.yml', '.toml', '.ini', '.conf')):
        return 'config'
    if name.endswith(('.py', '.sh')):
        return 'script'
    return 'other'

for root in roots:
    for p in root.rglob('*'):
        if p.is_file():
            counter[classify(p)] += 1

for key in sorted(counter):
    print(f'{key}: {counter[key]}')
PY

python3 - <<'PY' > "$OUTDIR/runtime-hashes.txt"
from pathlib import Path
import hashlib

targets = [
    Path('/home/agent/bin/project-research-run'),
    Path('/home/agent/bin/project-research-run.inner-step17-real-fetch-extraction'),
    Path('/home/agent/bin/validate-project-research-run'),
    Path('/home/agent/bin/project-research-eval'),
    Path('/home/agent/bin/project-research-regress'),
    Path('/home/agent/bin/project-research-regress-full'),
]

for p in targets:
    if p.exists():
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        print(f'{h}  {p}')
    else:
        print(f'MISSING  {p}')
PY

{
  section "SERVER FULL INVENTORY"
  echo "generated_at: $(date -Is)"
  echo "root_agents: $ROOT_AGENTS"
  echo "root_bin: $ROOT_BIN"

  section "GIT STATUS"
  cat "$OUTDIR/git-status.txt"

  section "GIT UNTRACKED"
  cat "$OUTDIR/git-untracked.txt"

  section "CLASSIFIED SUMMARY"
  cat "$OUTDIR/classified-summary.txt"

  section "RUNTIME HASHES"
  cat "$OUTDIR/runtime-hashes.txt"

  section "TOP LEVEL BIN FILES"
  sed -n '1,200p' "$OUTDIR/bin-files-detailed.txt"

  section "LARGE FILES > 1MB"
  sed -n '1,200p' "$OUTDIR/large-files.txt"

  section "BACKUP/TEMP FILES"
  sed -n '1,200p' "$OUTDIR/backup-temp-files.txt"

  section "CACHE DIRS"
  sed -n '1,200p' "$OUTDIR/cache-dirs.txt"

  section "AGENTS DIRS"
  sed -n '1,260p' "$OUTDIR/agents-dirs.txt"

  section "AGENTS FILES DETAILED (HEAD)"
  sed -n '1,260p' "$OUTDIR/agents-files-detailed.txt"

  section "LAST COMMITS"
  cat "$OUTDIR/git-log.txt"

  section "NEXT INTERPRETATION"
  echo "1) runtime-bin -> compare with repo coverage"
  echo "2) backup-temp / cache -> cleanup candidates"
  echo "3) large-files -> archive/LFS/manual review candidates"
  echo "4) other -> classify later into keep/archive/delete"
} > "$OUTDIR/REPORT.txt"

echo
echo "REPORT=$OUTDIR/REPORT.txt"
echo
sed -n '1,260p' "$OUTDIR/REPORT.txt"