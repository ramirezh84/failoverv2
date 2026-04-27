#!/usr/bin/env python3
"""Generate docs/profile-reference.md from profiles/profile.schema.json.
The CI job profile-doc-check diffs the regeneration against the committed
file and fails on drift."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "profiles" / "profile.schema.json"

HEADER = """# Profile Reference

**Audience:** Anyone authoring or modifying a per-app failover profile.
**Generated from:** `profiles/profile.schema.json`. Do not edit by hand —
run `uv run python scripts/generate_profile_reference.py > docs/profile-reference.md`.

This document is the field-by-field reference for the per-app YAML profile.
The orchestrator's runtime behavior is entirely driven by these fields; no
code change is required to onboard a new app.

See [`docs/onboarding-new-app.md`](onboarding-new-app.md) for the workflow,
and [`profiles/profile.schema.json`](../profiles/profile.schema.json) for the
machine-readable contract.

"""


def _emit_property(name: str, prop: dict[str, Any], required: bool, depth: int = 0) -> list[str]:
    indent = "  " * depth
    lines: list[str] = []
    type_str = prop.get("type", "any")
    if isinstance(type_str, list):
        type_str = " \\| ".join(type_str)
    enum = prop.get("enum")
    default = prop.get("default")
    desc = prop.get("description", "").strip()
    req_marker = " **(required)**" if required else ""
    lines.append(f"{indent}- **`{name}`** ({type_str}){req_marker}")
    if desc:
        lines.append(f"{indent}  {desc}")
    if enum is not None:
        lines.append(f"{indent}  Allowed: {', '.join(f'`{v}`' for v in enum)}.")
    if default is not None:
        lines.append(f"{indent}  Default: `{json.dumps(default)}`.")
    if prop.get("type") == "object" and "properties" in prop:
        sub_required = set(prop.get("required", []))
        for sub_name, sub_prop in prop["properties"].items():
            lines.extend(_emit_property(sub_name, sub_prop, sub_name in sub_required, depth + 1))
    if prop.get("type") == "array" and isinstance(prop.get("items"), dict):
        items = prop["items"]
        if items.get("enum"):
            lines.append(f"{indent}  Item enum: {', '.join(f'`{v}`' for v in items['enum'])}.")
    return lines


def main() -> int:
    if not SCHEMA.exists():
        # Match the placeholder committed in PR #1 verbatim so profile-doc-check
        # passes until the schema lands in PR #2.
        print(HEADER.rstrip())
        print()
        print("_Schema not yet committed; PR #2 will fill this in._")
        return 0
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    out: list[str] = [HEADER.rstrip()]
    out.append("\n## Top-level fields\n")
    required = set(schema.get("required", []))
    for name, prop in schema.get("properties", {}).items():
        out.extend(_emit_property(name, prop, name in required))
    out.append("")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
