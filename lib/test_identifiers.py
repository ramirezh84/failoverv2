from __future__ import annotations

from datetime import UTC, datetime

import pytest

from lib import identifiers


def test_failover_id_is_deterministic() -> None:
    ts = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
    a = identifiers.make_failover_id(app="test-app", direction="failover", timestamp=ts)
    b = identifiers.make_failover_id(app="test-app", direction="failover", timestamp=ts)
    assert a == b


def test_failover_id_changes_with_direction() -> None:
    ts = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
    a = identifiers.make_failover_id(app="x", direction="failover", timestamp=ts)
    b = identifiers.make_failover_id(app="x", direction="failback", timestamp=ts)
    assert a != b


def test_failover_id_changes_with_sequence() -> None:
    ts = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
    a = identifiers.make_failover_id(app="x", direction="failover", timestamp=ts, sequence=0)
    b = identifiers.make_failover_id(app="x", direction="failover", timestamp=ts, sequence=1)
    assert a != b


def test_unknown_direction_rejected() -> None:
    ts = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="direction must be"):
        identifiers.make_failover_id(app="x", direction="oops", timestamp=ts)


def test_long_app_name_truncated_within_step_functions_limit() -> None:
    ts = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
    long_app = "a" * 100
    name = identifiers.make_failover_id(app=long_app, direction="failover", timestamp=ts)
    assert len(name) <= 80
