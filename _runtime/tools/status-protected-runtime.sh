#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/agent/agents/_runtime"
CANONICAL="$ROOT/canonical"
BIN_SRC="/home/agent/bin"
LIST="$CANONICAL/meta/protected-working-set.txt"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

if [[ ! -f "$LIST" ]]; then
  echo "ERROR: missing protected working set list: $LIST" >&2
  exit 1
fi

echo "== protected runtime status =="
echo "source   : $BIN_SRC"
echo "canonical: $CANONICAL/bin"
echo "filelist : $LIST"
echo

echo "== precheck =="
missing_src=0
missing_can=0
while IFS= read -r n; do
  [[ -n "$n" ]] || continue
  if [[ ! -e "$BIN_SRC/$n" ]]; then
    echo "MISSING_SOURCE   $n"
    missing_src=1
  fi
  if [[ ! -e "$CANONICAL/bin/$n" ]]; then
    echo "MISSING_CANONICAL $n"
    missing_can=1
  fi
done < "$LIST"

if [[ "$missing_src" -ne 0 || "$missing_can" -ne 0 ]]; then
  echo
  echo "STATUS=BROKEN"
  exit 2
fi

echo "PRECHECK_OK"
echo

while IFS= read -r n; do
  [[ -n "$n" ]] || continue
  sha256sum "$BIN_SRC/$n"
done < "$LIST" | sed 's#/home/agent/bin/##' | sort > "$TMPDIR/src.sha256"

while IFS= read -r n; do
  [[ -n "$n" ]] || continue
  sha256sum "$CANONICAL/bin/$n"
done < "$LIST" | sed "s#$CANONICAL/bin/##" | sort > "$TMPDIR/canonical.sha256"

echo "== diff =="
if diff -u "$TMPDIR/src.sha256" "$TMPDIR/canonical.sha256" > "$TMPDIR/diff.txt"; then
  echo "STATUS=IN_SYNC"
  echo "All protected files match."
  echo
  echo "files checked: $(wc -l < "$LIST" | tr -d ' ')"
  exit 0
fi

echo "STATUS=DRIFT"
echo
sed -n '1,220p' "$TMPDIR/diff.txt"
echo

echo "== changed files =="
awk '
/^\-\-/ {next}
/^\+\+/ {next}
/^@@/ {next}
/^-/ {print $2}
/^\+/ {print $2}
' "$TMPDIR/diff.txt" | sort -u
echo

echo "files checked: $(wc -l < "$LIST" | tr -d ' ')"
exit 1