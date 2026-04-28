#!/usr/bin/env python3
"""Reject IAM policies in Terraform sources that contain wildcard actions or
resources. Required by CLAUDE.md §2 hard constraint #5 and SPEC.md §11.5."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TERRAFORM_DIR = ROOT / "terraform"

# Match `Action = "*"` or `Action = ["*"]` or `actions = ["*"]` (case-insensitive)
_ACTION_WILDCARD = re.compile(
    r'(?i)\b(?:action|actions)\b\s*=\s*\[?\s*"\*"',
)
_RESOURCE_WILDCARD = re.compile(
    r'(?i)\b(?:resource|resources)\b\s*=\s*\[?\s*"\*"',
)


_ALLOW_DIRECTIVE = "iam-policy-check: allow-wildcard"


def main() -> int:
    if not TERRAFORM_DIR.exists():
        print(f"{TERRAFORM_DIR} does not exist; nothing to check.")
        return 0

    findings: list[str] = []
    for tf_file in TERRAFORM_DIR.rglob("*.tf"):
        text = tf_file.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            if _ACTION_WILDCARD.search(line):
                # Action wildcards are NEVER allowed.
                findings.append(f"{tf_file.relative_to(ROOT)}:{lineno}: {stripped}")
                continue
            if _RESOURCE_WILDCARD.search(line) and _ALLOW_DIRECTIVE not in line:
                findings.append(f"{tf_file.relative_to(ROOT)}:{lineno}: {stripped}")

    if findings:
        print("IAM wildcard usage forbidden (CLAUDE.md §2):")
        for f in findings:
            print(f"  {f}")
        print(
            "\nIf an AWS action genuinely does not support resource-level scoping, append "
            "`# iam-policy-check: allow-wildcard <reason>` to the offending line AND ensure "
            "the policy statement uses a Condition to bound the access."
        )
        return 1
    print(
        f"OK: scanned {sum(1 for _ in TERRAFORM_DIR.rglob('*.tf'))} terraform files; no wildcards."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
