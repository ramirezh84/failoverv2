"""Helpers for the deterministic identifiers required by CLAUDE.md §3.1.

A ``failover_id`` is the Step Functions execution name and the dedupe key for
every Lambda invoked by the state machine. Same input → same id.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

_MAX_NAME_LEN = 80  # Step Functions execution name limit


def make_failover_id(
    *,
    app: str,
    direction: str,
    timestamp: datetime,
    sequence: int = 0,
) -> str:
    """Produce a deterministic Step Functions execution name.

    Format: ``failover-<app>-<UTC-date>-<direction>-<seq>-<short-hash>``.
    The short hash makes the name unique within a UTC day even if two
    operators trigger at the same minute.
    """
    if direction not in {"failover", "failback", "dryrun"}:
        raise ValueError(f"direction must be failover|failback|dryrun, got {direction!r}")
    utc = timestamp.astimezone(UTC)
    date_part = utc.strftime("%Y%m%d")
    seed = f"{app}|{direction}|{utc.isoformat()}|{sequence}".encode()
    short = hashlib.blake2b(seed, digest_size=4).hexdigest()
    name = f"failover-{app}-{date_part}-{direction}-{sequence:03d}-{short}"
    if len(name) > _MAX_NAME_LEN:
        # Truncate the app component if needed
        budget = _MAX_NAME_LEN - len(name) + len(app)
        app_part = app[:budget]
        name = f"failover-{app_part}-{date_part}-{direction}-{sequence:03d}-{short}"
    return name


__all__ = ["make_failover_id"]
