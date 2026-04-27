#!/usr/bin/env bash
# Run `terraform validate` against every root module under terraform/apps/.
# Initialises with `-backend=false` so no AWS credentials are required.
# SPEC.md §11.5 requirement.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPS_DIR="$ROOT/terraform/apps"

if [[ ! -d "$APPS_DIR" ]]; then
  echo "No terraform/apps directory yet; nothing to validate."
  exit 0
fi

failures=0
while IFS= read -r module; do
  echo "==> $(realpath --relative-to="$ROOT" "$module")"
  pushd "$module" >/dev/null
  terraform init -backend=false -input=false -no-color >/dev/null
  if ! terraform validate -no-color; then
    failures=$((failures + 1))
  fi
  popd >/dev/null
done < <(find "$APPS_DIR" -mindepth 1 -maxdepth 3 -type d -exec test -e {}/main.tf \; -print)

if [[ $failures -ne 0 ]]; then
  echo "$failures module(s) failed validation."
  exit 1
fi
echo "All modules validated."
