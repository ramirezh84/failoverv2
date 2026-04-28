#!/usr/bin/env bash
# Re-render every docs/diagrams/*.py and verify the render succeeds and
# emits both PNG and SVG outputs. We intentionally do NOT bytewise-diff
# against committed renders: graphviz output is non-deterministic across
# OS/version (font hints, anti-aliasing, embedded timestamps), so byte
# equality across macOS dev machines and Ubuntu CI is impractical. The
# committed PNG/SVG are reference snapshots for inline doc embedding;
# their job is to render readable in GitHub, not to be byte-identical
# every CI run.
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
  ( cd "$outdir" && mkdir -p docs/diagrams && PYTHONPATH="$OLDPWD" uv --project "$OLDPWD" run python "$OLDPWD/$src" )
  for ext in png svg; do
    fresh="$outdir/$DIAGRAMS_DIR/$base.$ext"
    if [ ! -f "$fresh" ] || [ ! -s "$fresh" ]; then
      echo "::error file=$src::$base.$ext did not render or is empty"
      fail=$((fail + 1))
      continue
    fi
    committed="$DIAGRAMS_DIR/$base.$ext"
    if [ ! -f "$committed" ]; then
      echo "::warning::$committed missing; render locally with 'uv run python $src' and commit."
    fi
  done
done

if [ "$fail" -ne 0 ]; then exit 1; fi
echo "OK: every docs/diagrams/*.py renders successfully."
