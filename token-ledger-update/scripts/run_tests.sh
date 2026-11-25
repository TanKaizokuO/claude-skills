#!/bin/bash
# Run the offline page tests against a built artifact page.
#
# Usage: run_tests.sh <artifact-page.html> <out-dir>
#   Logs:  <out-dir>/tests.log   (also prints a short summary at the end)
#   Flag:  <out-dir>/tests.done  containing "exit N" when all tests finished
#   Shots: <out-dir>/offline-*.png
#
# Run in the background and check the flag once. Do not sleep-poll:
#   scripts/run_tests.sh <page> <out-dir> > /dev/null 2>&1 &
# Pass criteria (read from the log): 0 page errors, 0 external network requests,
# RESULT: ALL PASS from test_downloads and test_speed_scopes.
# test_artifact and money2 print values for review; they do not fail on them.

set -u
PAGE_ARG="${1:?usage: run_tests.sh <artifact-page.html> <out-dir>}"
OUT="${2:?usage: run_tests.sh <artifact-page.html> <out-dir>}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"

mkdir -p "$OUT"
PAGE_ABS="$(cd "$(dirname "$PAGE_ARG")" && pwd)/$(basename "$PAGE_ARG")"
LOG="$OUT/tests.log"
DONE="$OUT/tests.done"
rm -f "$DONE"

cd "$HERE" || exit 1
export PAGE="$PAGE_ABS" SHOT_DIR="$OUT" SHOT="offline"
{
  echo "== test_artifact";   "$PY" test_artifact.py
  echo "== money2";          "$PY" money2.py "$PAGE_ABS"
  echo "== inspect_summary"; "$PY" inspect_summary.py
  echo "== test_downloads";  "$PY" test_downloads.py
  echo "== test_speed_scopes"; "$PY" test_speed_scopes.py
} > "$LOG" 2>&1
RC=$?
echo "exit $RC" > "$DONE"

echo "--- summary"
grep -E "^(errors:|external network requests blocked:|snapshot misses:|RESULT:)|^FAIL " "$LOG" || true
exit "$RC"
