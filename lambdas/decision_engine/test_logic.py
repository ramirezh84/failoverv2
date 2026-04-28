from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lambdas.decision_engine import logic
from lib.profile_loader import Profile, load_from_path

PROFILE = load_from_path("profiles/test-app.yaml")


def _profile_with(**overrides: object) -> Profile:
    """Return PROFILE with a few overridable fields."""
    data = PROFILE.model_dump()
    for k, v in overrides.items():
        section, _, key = k.partition(".")
        if key:
            data[section][key] = v
        else:
            data[section] = v
    return Profile.model_validate(data)


def _now() -> datetime:
    return datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)


def test_green_when_no_red_signals() -> None:
    e = logic.evaluate(
        profile=PROFILE,
        primary_red_signals=[],
        primary_red_history=[],
        last_decision_at=None,
        now=_now(),
        secondary_ready=lambda: True,
    )
    assert e.state == "GREEN"
    assert not e.failover_authorized


def test_watching_when_one_red_below_quorum() -> None:
    e = logic.evaluate(
        profile=PROFILE,  # tier1_quorum=2
        primary_red_signals=["nlb"],
        primary_red_history=[True] * 10,
        last_decision_at=None,
        now=_now(),
        secondary_ready=lambda: True,
    )
    assert e.state == "WATCHING"
    assert e.reason == "quorum_not_held"


def test_watching_when_dwell_not_held_yet() -> None:
    e = logic.evaluate(
        profile=PROFILE,  # dwell=5
        primary_red_signals=["nlb", "canary"],
        primary_red_history=[True, True, True],  # only 3 minutes red
        last_decision_at=None,
        now=_now(),
        secondary_ready=lambda: True,
    )
    assert e.state == "WATCHING"
    assert e.reason == "dwell_not_held"


def test_blocked_by_hysteresis() -> None:
    last = _now() - timedelta(minutes=1)  # hysteresis is 3 minutes
    e = logic.evaluate(
        profile=PROFILE,
        primary_red_signals=["nlb", "canary"],
        primary_red_history=[True] * 10,
        last_decision_at=last,
        now=_now(),
        secondary_ready=lambda: True,
    )
    assert e.state == "WATCHING"
    assert e.reason == "hysteresis_blocked"


def test_failover_authorized_but_not_auto_when_disabled() -> None:
    profile = _profile_with(**{"failover.auto_failover": False})
    e = logic.evaluate(
        profile=profile,
        primary_red_signals=["nlb", "canary"],
        primary_red_history=[True] * 10,
        last_decision_at=_now() - timedelta(hours=1),
        now=_now(),
        secondary_ready=lambda: True,
    )
    assert e.state == "FAILOVER_AUTHORIZED_BUT_NOT_AUTO"
    assert e.failover_authorized is True


def test_failover_authorized_but_unsafe_when_secondary_not_ready() -> None:
    profile = _profile_with(**{"failover.auto_failover": True})
    e = logic.evaluate(
        profile=profile,
        primary_red_signals=["nlb", "canary"],
        primary_red_history=[True] * 10,
        last_decision_at=_now() - timedelta(hours=1),
        now=_now(),
        secondary_ready=lambda: False,
    )
    assert e.state == "FAILOVER_AUTHORIZED_BUT_UNSAFE"
    assert e.failover_authorized is True
    assert e.secondary_safe is False


def test_failover_authorized_when_all_gates_pass() -> None:
    profile = _profile_with(**{"failover.auto_failover": True})
    e = logic.evaluate(
        profile=profile,
        primary_red_signals=["nlb", "canary"],
        primary_red_history=[True] * 10,
        last_decision_at=_now() - timedelta(hours=1),
        now=_now(),
        secondary_ready=lambda: True,
    )
    assert e.state == "FAILOVER_AUTHORIZED"
    assert e.failover_authorized is True


@pytest.mark.parametrize("history", [[], [False] * 10, [True] * 4])
def test_dwell_helper_rejects_short_or_mixed(history: list[bool]) -> None:
    assert logic._dwell_held(history, dwell_minutes=5) is False


def test_dwell_helper_accepts_full_red_window() -> None:
    assert logic._dwell_held([True] * 5, dwell_minutes=5) is True


def test_hysteresis_first_decision_always_allowed() -> None:
    assert logic._hysteresis_held(None, _now(), 3) is True
