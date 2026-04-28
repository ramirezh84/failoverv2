#!/usr/bin/env bash
# Extract every ```mermaid block from .md files and parse with mmdc.
# SPEC.md §11.5 mermaid-validate job.
set -euo pipefail

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

files=$(find docs runbooks -name '*.md' -type f 2>/dev/null || true)
for top in README.md ARCHITECTURE.md CONTRIBUTING.md SECURITY.md; do
  [ -f "$top" ] && files="$files $top"
done

count=0
fail=0
for f in $files; do
  [ -f "$f" ] || continue
  awk -v fname="$f" -v outdir="$tmpdir" '
    /^```mermaid/ { inblock=1; idx++; out=sprintf("%s/%s.%d.mmd", outdir, gensub("/","_","g",fname), idx); next }
    /^```/ && inblock { inblock=0; next }
    inblock { print >> out }
  ' "$f"
done

while IFS= read -r mmd; do
  [ -n "$mmd" ] || continue
  count=$((count + 1))
  if ! npx --yes -p @mermaid-js/mermaid-cli@10.9.1 mmdc -i "$mmd" -o "$mmd.svg" 2>/tmp/mmd-err.log; then
    echo "::error::Mermaid parse failed in $(basename "$mmd")"
    cat /tmp/mmd-err.log
    fail=$((fail + 1))
  fi
done < <(find "$tmpdir" -name '*.mmd' -type f 2>/dev/null)

if [ "$fail" -ne 0 ]; then
  echo "$fail Mermaid block(s) failed to parse."
  exit 1
fi
echo "OK: $count Mermaid block(s) parsed cleanly."
