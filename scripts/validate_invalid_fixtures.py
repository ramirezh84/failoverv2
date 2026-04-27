#!/usr/bin/env python3
"""Every YAML in tests/unit/profile_validation/invalid/ MUST be rejected by
the schema. CI fails if any fixture is silently accepted, which would mean a
schema constraint regressed."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "profiles" / "profile.schema.json"
INVALID_DIR = ROOT / "tests" / "unit" / "profile_validation" / "invalid"


def main() -> int:
    if not SCHEMA.exists() or not INVALID_DIR.exists():
        print("Schema or invalid-fixture directory not present yet; skipping.")
        return 0
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    silently_accepted: list[str] = []
    checked = 0
    for path in sorted(INVALID_DIR.glob("*.yaml")):
        checked += 1
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            # YAML parse errors are an acceptable form of rejection.
            continue
        errors = list(validator.iter_errors(doc))
        if not errors:
            silently_accepted.append(str(path.relative_to(ROOT)))
    if silently_accepted:
        print("These invalid fixtures were silently accepted (schema regression):")
        for f in silently_accepted:
            print(f"  {f}")
        return 1
    print(f"OK: all {checked} invalid fixtures correctly rejected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
