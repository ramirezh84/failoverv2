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
  # uv needs to find pyproject.toml; --project pins it. The script (.py) is
  # invoked with the project root as cwd so its `filename = "docs/diagrams/..."`
  # writes into the work directory under the right relative path.
  ( cd "$outdir" && mkdir -p docs/diagrams && PYTHONPATH="$OLDPWD" uv --project "$OLDPWD" run python "$OLDPWD/$src" )
  for ext in png svg; do
    fresh="$outdir/$DIAGRAMS_DIR/$base.$ext"
    committed="$DIAGRAMS_DIR/$base.$ext"
    [ -f "$fresh" ] || continue
    if [ ! -f "$committed" ]; then
      # PNG/SVG not yet committed — diagram source landed without a render.
      # Warn but don't fail; the next render commits the binary.
      echo "::warning::$committed missing; render with 'uv run python $src' and commit."
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
