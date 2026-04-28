"""Decision Engine logic.

Encodes SPEC §4.2:

    FAILOVER_AUTHORIZED = (
        count(Tier1 red) >= profile.tier1_quorum
        AND duration(red continuously) >= profile.dwell_minutes
        AND time_since_last_decision >= profile.hysteresis_minutes
        AND profile.auto_failover == true
    )

Pure-Python; the AWS reader callables are injected so unit tests can drive
the rule directly without mocks.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from lib.profile_loader import Profile

DecisionState = Literal[
    "GREEN",
    "WATCHING",
    "FAILOVER_AUTHORIZED",
    "FAILOVER_AUTHORIZED_BUT_NOT_AUTO",
    "FAILOVER_AUTHORIZED_BUT_UNSAFE",
]


@dataclass(frozen=True)
class Evaluation:
    state: DecisionState
    reason: str
    tier1_red_signals: tuple[str, ...]
    quorum_held: bool
    dwell_held: bool
    hysteresis_held: bool
    secondary_safe: bool
    failover_authorized: bool


def _quorum_held(red_signals: list[str], required: int) -> bool:
    return len(red_signals) >= required


def _dwell_held(
    red_history: list[bool],
    *,
    samples_per_minute: int = 1,
    dwell_minutes: int,
) -> bool:
    """All samples in the trailing dwell window must be red.

    ``red_history`` is the list of "is the quorum red?" booleans, oldest first.
    The Decision Engine runs every minute, so ``samples_per_minute=1``; tests
    can override.
    """
    samples = dwell_minutes * samples_per_minute
    if len(red_history) < samples:
        return False
    return all(red_history[-samples:])


def _hysteresis_held(
    last_decision_at: datetime | None, now: datetime, hysteresis_minutes: int
) -> bool:
    if last_decision_at is None:
        return True
    return now - last_decision_at >= timedelta(minutes=hysteresis_minutes)


def evaluate(
    *,
    profile: Profile,
    primary_red_signals: list[str],
    primary_red_history: list[bool],
    last_decision_at: datetime | None,
    now: datetime,
    secondary_ready: Callable[[], bool],
) -> Evaluation:
    """Apply the §4.2 rule and return a structured Evaluation."""
    quorum = _quorum_held(primary_red_signals, profile.signals.tier1_quorum)
    dwell = _dwell_held(
        primary_red_history,
        dwell_minutes=profile.signals.dwell_minutes,
    )
    hyst = _hysteresis_held(last_decision_at, now, profile.signals.hysteresis_minutes)
    secondary_safe = secondary_ready() if quorum and dwell else True

    if not quorum:
        return Evaluation(
            state="GREEN" if not primary_red_signals else "WATCHING",
            reason="quorum_not_held",
            tier1_red_signals=tuple(primary_red_signals),
            quorum_held=quorum,
            dwell_held=dwell,
            hysteresis_held=hyst,
            secondary_safe=secondary_safe,
            failover_authorized=False,
        )
    if not dwell:
        return Evaluation(
            state="WATCHING",
            reason="dwell_not_held",
            tier1_red_signals=tuple(primary_red_signals),
            quorum_held=quorum,
            dwell_held=dwell,
            hysteresis_held=hyst,
            secondary_safe=secondary_safe,
            failover_authorized=False,
        )
    if not hyst:
        return Evaluation(
            state="WATCHING",
            reason="hysteresis_blocked",
            tier1_red_signals=tuple(primary_red_signals),
            quorum_held=quorum,
            dwell_held=dwell,
            hysteresis_held=hyst,
            secondary_safe=secondary_safe,
            failover_authorized=False,
        )

    if not profile.failover.auto_failover:
        return Evaluation(
            state="FAILOVER_AUTHORIZED_BUT_NOT_AUTO",
            reason="auto_failover_disabled_alert_only",
            tier1_red_signals=tuple(primary_red_signals),
            quorum_held=quorum,
            dwell_held=dwell,
            hysteresis_held=hyst,
            secondary_safe=secondary_safe,
            failover_authorized=True,
        )
    if not secondary_safe:
        return Evaluation(
            state="FAILOVER_AUTHORIZED_BUT_UNSAFE",
            reason="secondary_not_ready",
            tier1_red_signals=tuple(primary_red_signals),
            quorum_held=quorum,
            dwell_held=dwell,
            hysteresis_held=hyst,
            secondary_safe=secondary_safe,
            failover_authorized=True,
        )
    return Evaluation(
        state="FAILOVER_AUTHORIZED",
        reason="all_gates_passed",
        tier1_red_signals=tuple(primary_red_signals),
        quorum_held=quorum,
        dwell_held=dwell,
        hysteresis_held=hyst,
        secondary_safe=secondary_safe,
        failover_authorized=True,
    )


__all__ = ["Evaluation", "evaluate"]
