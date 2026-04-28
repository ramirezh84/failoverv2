#!/usr/bin/env python3
"""Every aws_lambda_function resource must have a vpc_config block.
Required by CLAUDE.md §2 hard constraint #4 and SPEC.md §11.5."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TERRAFORM_DIR = ROOT / "terraform"

_LAMBDA_RESOURCE = re.compile(
    r'resource\s+"aws_lambda_function"\s+"([^"]+)"\s*\{',
)


def _find_block_end(text: str, start: int) -> int:
    """Return index just past the matching closing brace for a `{` at start."""
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def main() -> int:
    if not TERRAFORM_DIR.exists():
        print(f"{TERRAFORM_DIR} does not exist; nothing to check.")
        return 0

    failures: list[str] = []
    checked = 0

    for tf_file in TERRAFORM_DIR.rglob("*.tf"):
        text = tf_file.read_text(encoding="utf-8")
        for match in _LAMBDA_RESOURCE.finditer(text):
            checked += 1
            name = match.group(1)
            brace_idx = text.find("{", match.end() - 1)
            end_idx = _find_block_end(text, brace_idx)
            if end_idx == -1:
                failures.append(f"{tf_file.relative_to(ROOT)}: '{name}' unbalanced braces")
                continue
            body = text[brace_idx + 1 : end_idx - 1]
            if not re.search(r"\bvpc_config\s*\{", body):
                failures.append(f"{tf_file.relative_to(ROOT)}: '{name}' missing vpc_config block")

    if failures:
        print("Lambda functions missing vpc_config (CLAUDE.md §2):")
        for f in failures:
            print(f"  {f}")
        return 1
    print(f"OK: checked {checked} aws_lambda_function resources; all have vpc_config.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
