#!/usr/bin/env bash
# Every boto3.client(...) and boto3.resource(...) in lambdas/ and lib/ must
# pass an explicit endpoint_url= keyword. The lib.aws_clients factories are
# the only sanctioned construction site. CLAUDE.md §2 hard constraint #4.
set -euo pipefail

bad=0
# lib/aws_clients.py is the sanctioned factory — its calls span multiple
# lines with endpoint_url on a subsequent line, so the line-grep would false
# positive. Every other Python file under lambdas/ + lib/ is checked.
files=$(find lambdas lib -name '*.py' -type f \
        ! -name 'test_*.py' ! -name 'conftest.py' \
        ! -path 'lib/aws_clients.py' 2>/dev/null || true)

for f in $files; do
  while IFS=: read -r lineno match; do
    [ -z "${lineno:-}" ] && continue
    stripped="$(printf '%s' "$match" | sed -E 's/^[[:space:]]+//')"
    case "$stripped" in
      \#*) continue ;;
    esac
    if ! printf '%s' "$match" | grep -q 'endpoint_url='; then
      printf '%s:%s: %s\n' "$f" "$lineno" "$match"
      bad=1
    fi
  done < <(grep -nE 'boto3\.(client|resource)\(' "$f" || true)
done

if [ "$bad" -ne 0 ]; then
  echo
  echo "boto3.client/resource without endpoint_url= forbidden (CLAUDE.md §2)."
  echo "Use the lib.aws_clients factories."
  exit 1
fi
echo "OK: all boto3.client/resource constructions pass endpoint_url=."
