#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/runtime-paths.sh"

REPO_ROOT="$(runtime_repo_root)"
ROOT="$REPO_ROOT/_runtime"
CANONICAL="$ROOT/canonical"
BIN_SRC="$(runtime_bin_dir)"
LIST="$CANONICAL/meta/protected-working-set.txt"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

if [[ ! -f "$LIST" ]]; then
  echo "ERROR: missing protected working set list: $LIST" >&2
  exit 1
fi

mkdir -p "$CANONICAL/bin" "$CANONICAL/meta"

echo "== sync protected runtime =="
echo "repo_root: $REPO_ROOT"
echo "source   : $BIN_SRC"
echo "target   : $CANONICAL/bin"
echo "filelist : $LIST"
echo

echo "== precheck: required source files =="
while IFS= read -r n; do
  [[ -n "$n" ]] || continue
  if [[ ! -e "$BIN_SRC/$n" ]]; then
    echo "ERROR: missing source file: $BIN_SRC/$n" >&2
    exit 1
  fi
done < "$LIST"
echo "PRECHECK_OK"
echo

echo "== copy =="
while IFS= read -r n; do
  [[ -n "$n" ]] || continue
  cp -a "$BIN_SRC/$n" "$CANONICAL/bin/$n"
  echo "copied: $n"
done < "$LIST"
echo

echo "== build hashes from source =="
: > "$TMPDIR/src.sha256"
while IFS= read -r n; do
  [[ -n "$n" ]] || continue
  sha256sum "$BIN_SRC/$n"
done < "$LIST" | sed "s#$BIN_SRC/##" | sort > "$TMPDIR/src.sha256"

echo "== build hashes from canonical =="
: > "$TMPDIR/canonical.sha256"
while IFS= read -r n; do
  [[ -n "$n" ]] || continue
  sha256sum "$CANONICAL/bin/$n"
done < "$LIST" | sed "s#$CANONICAL/bin/##" | sort > "$TMPDIR/canonical.sha256"

cp "$TMPDIR/src.sha256" "$CANONICAL/meta/src-from-bin.sha256"
cp "$TMPDIR/canonical.sha256" "$CANONICAL/meta/canonical.sha256"

echo
echo "== verify hash parity =="
diff -u "$CANONICAL/meta/src-from-bin.sha256" "$CANONICAL/meta/canonical.sha256"
echo "HASH_OK"
echo

echo "== summary =="
COUNT="$(wc -l < "$LIST" | tr -d ' ')"
echo "files synced: $COUNT"
echo "meta updated:"
echo "- $CANONICAL/meta/src-from-bin.sha256"
echo "- $CANONICAL/meta/canonical.sha256"
