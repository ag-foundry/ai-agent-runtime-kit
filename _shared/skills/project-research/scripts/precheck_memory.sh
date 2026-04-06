#!/usr/bin/env bash
set -euo pipefail

TOPIC="${1:-}"
if [[ -z "$TOPIC" ]]; then
  echo "Usage: precheck_memory.sh <topic>" >&2
  exit 1
fi

echo "== precheck: topic =="
echo "$TOPIC"
echo

if command -v memory >/dev/null 2>&1; then
  echo "== memory search =="
  memory search "$TOPIC" || true
  echo
else
  echo "memory command not found; skipping memory search"
  echo
fi

echo "== local files hint =="
echo "Review current topic files if present: README.md LOG.md TODO.md DECISIONS/ artifacts/"
