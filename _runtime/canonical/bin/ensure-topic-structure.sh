#!/usr/bin/env bash
set -euo pipefail

TOPIC="${1:-}"
QUIET="${2:-}"

if [[ -z "$TOPIC" ]]; then
  echo "Usage: ensure-topic-structure.sh <topic> [--quiet]" >&2
  exit 1
fi

BASE="/home/agent/agents"
DIR="$BASE/$TOPIC"

mkdir -p "$DIR"
mkdir -p "$DIR/artifacts"
mkdir -p "$DIR/runs"
mkdir -p "$DIR/memory"
mkdir -p "$DIR/DECISIONS"

[[ -f "$DIR/README.md" ]] || printf '# %s\n\n' "$TOPIC" > "$DIR/README.md"
[[ -f "$DIR/LOG.md" ]] || printf '# %s\n\n' "$TOPIC" > "$DIR/LOG.md"
[[ -f "$DIR/TODO.md" ]] || printf '# TODO\n\n- [ ] Цель темы\n' > "$DIR/TODO.md"

if [[ ! -f "$DIR/AGENTS.md" ]]; then
  cat > "$DIR/AGENTS.md" <<EOF
# Правила темы (workspace)

- Работать только в этой папке.
- Вести LOG.md.
- Память: ./memory и ../_shared/memory
- Системные изменения — только по явному запросу пользователя.
EOF
fi

[[ -f "$DIR/memory/context.md" ]] || printf '# context\n\n' > "$DIR/memory/context.md"
[[ -f "$DIR/memory/facts.md" ]] || printf '# facts\n\n' > "$DIR/memory/facts.md"
[[ -f "$DIR/memory/refs.md" ]] || printf '# refs\n\n' > "$DIR/memory/refs.md"
[[ -f "$DIR/memory/lessons.md" ]] || printf '# lessons\n\n' > "$DIR/memory/lessons.md"
[[ -f "$DIR/memory/index.md" ]] || printf '# index\n\n' > "$DIR/memory/index.md"

if [[ "$QUIET" != "--quiet" ]]; then
  echo "ensured: $DIR"
  echo "created/verified:"
  echo "- $DIR/README.md"
  echo "- $DIR/LOG.md"
  echo "- $DIR/TODO.md"
  echo "- $DIR/AGENTS.md"
  echo "- $DIR/artifacts/"
  echo "- $DIR/runs/"
  echo "- $DIR/DECISIONS/"
  echo "- $DIR/memory/context.md"
  echo "- $DIR/memory/facts.md"
  echo "- $DIR/memory/refs.md"
  echo "- $DIR/memory/lessons.md"
  echo "- $DIR/memory/index.md"
fi
