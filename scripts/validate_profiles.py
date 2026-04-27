#!/usr/bin/env python3
"""Validate every profile under profiles/ against profile.schema.json.
Used by CI job profile-schema-validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "profiles"
SCHEMA = PROFILES / "profile.schema.json"


def main() -> int:
    if not SCHEMA.exists():
        print(f"{SCHEMA} not present yet; skipping.")
        return 0
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    failures: list[str] = []
    checked = 0
    for path in sorted(PROFILES.glob("*.yaml")):
        if path.name.startswith("."):
            continue
        checked += 1
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            failures.append(f"{path.relative_to(ROOT)}: YAML parse error: {exc}")
            continue
        errors = sorted(validator.iter_errors(doc), key=lambda e: e.path)
        if errors:
            for err in errors:
                where = "/".join(str(p) for p in err.absolute_path) or "<root>"
                failures.append(f"{path.relative_to(ROOT)}: {where}: {err.message}")
    if failures:
        print("Profile validation failures:")
        for f in failures:
            print(f"  {f}")
        return 1
    print(f"OK: validated {checked} profile(s) against schema.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
