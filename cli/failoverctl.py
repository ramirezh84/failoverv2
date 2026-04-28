"""Placeholder entrypoint for the failoverctl CLI; full implementation in
PR #5 per SPEC §8.5."""

from __future__ import annotations

import sys


def main() -> int:
    sys.stderr.write("failoverctl: not yet implemented (see SPEC §8.5)\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
