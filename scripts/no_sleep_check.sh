#!/usr/bin/env bash
# No time.sleep in Lambda code. Use Step Functions Wait states. CLAUDE.md §3.1.
set -euo pipefail

bad=0
files=$(find lambdas -name '*.py' -type f ! -name 'test_*.py' 2>/dev/null || true)
for f in $files; do
  if grep -nE '\btime\.sleep\b' "$f" >/dev/null 2>&1; then
    grep -nE '\btime\.sleep\b' "$f" | sed "s|^|$f:|"
    bad=1
  fi
done

if [ "$bad" -ne 0 ]; then
  echo
  echo "time.sleep is forbidden in Lambdas. Use Step Functions Wait states."
  exit 1
fi
echo "OK: no time.sleep in lambdas/."
