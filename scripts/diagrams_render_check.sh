#!/usr/bin/env bash
# Re-render every docs/diagrams/*.py and diff PNG/SVG against committed.
# SPEC.md §11.5 diagrams-render-check job.
set -euo pipefail

DIAGRAMS_DIR="docs/diagrams"
[ -d "$DIAGRAMS_DIR" ] || { echo "No $DIAGRAMS_DIR yet."; exit 0; }

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

fail=0
srcs=$(find "$DIAGRAMS_DIR" -maxdepth 1 -name '*.py' -type f 2>/dev/null || true)
for src in $srcs; do
  [ -f "$src" ] || continue
  base="$(basename "$src" .py)"
  outdir="$work/$base"
  mkdir -p "$outdir"
  ( cd "$outdir" && uv run python "$OLDPWD/$src" )
  for ext in png svg; do
    fresh="$outdir/$base.$ext"
    committed="$DIAGRAMS_DIR/$base.$ext"
    [ -f "$fresh" ] || continue
    if [ ! -f "$committed" ]; then
      echo "::error::$committed missing; commit the rendered output."
      fail=$((fail + 1))
      continue
    fi
    if ! cmp -s "$fresh" "$committed"; then
      echo "::error file=$src::$base.$ext drift; re-render and commit."
      fail=$((fail + 1))
    fi
  done
done

if [ "$fail" -ne 0 ]; then exit 1; fi
echo "OK: all diagrams render identically to committed PNG/SVG."
