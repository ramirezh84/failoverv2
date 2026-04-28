"""Scenario 03: Single AZ outage in primary. Surviving AZ keeps NLB > 0. NO failover.

See ``docs/scenarios/scenario-03-single-az-outage.md`` for the full minute-by-minute
walkthrough and assertion rationale (SPEC §8.6.3).

This test runs against a deployed test harness (`make harness-up` first).
"""

from __future__ import annotations

import pytest

from tests.chaos import framework as fw

pytestmark = pytest.mark.chaos


def test_scenario_03() -> None:
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
        name="scenario-03-single-az-outage",
        setup=setup,
        wait_seconds=90,
        assertions=assertions,
        cleanup=cleanup,
    )
    assert result.passed, "\n".join(result.failures)
