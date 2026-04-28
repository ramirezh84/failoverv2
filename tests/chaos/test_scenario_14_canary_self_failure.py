"""Scenario 14: Synthetic canary itself fails. Single signal red; no quorum -> no failover. SNS canary degraded alert.

See ``docs/scenarios/scenario-14-canary-self-failure.md`` for the full minute-by-minute
walkthrough and assertion rationale (SPEC §8.6.3).

This test runs against a deployed test harness (`make harness-up` first).
"""

from __future__ import annotations

import pytest

from tests.chaos import framework as fw

pytestmark = pytest.mark.chaos


def test_scenario_14() -> None:
    def setup() -> None:
        fw.reset_orchestrator_state()
        # Non-mutating: signal injection only.
        fw.force_signal_red("outer_nlb_unhealthy", 0.0)

    def assertions() -> dict[str, callable]:
        return {
            "primary_role_active": lambda: fw.assert_indicator_role(fw.PRIMARY_REGION, "ACTIVE"),
            "primary_alarm_ok": lambda: fw.assert_alarm_state(
                f"{fw.APP}-PrimaryHealthControl-use1", fw.PRIMARY_REGION, "OK"
            ),
        }

    def cleanup() -> None:
        fw.reset_orchestrator_state()
        # nothing to clean — no real state changes

    result = fw.run_scenario(
        name="scenario-14-canary-self-failure",
        setup=setup,
        wait_seconds=90,
        assertions=assertions,
        cleanup=cleanup,
    )
    assert result.passed, "\n".join(result.failures)
