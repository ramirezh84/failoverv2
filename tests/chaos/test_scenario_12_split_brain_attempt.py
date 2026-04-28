"""Scenario 12: Both regions briefly write to SSM concurrently. Indicator state-machine guard prevents both ACTIVE.

See ``docs/scenarios/scenario-12-split-brain-attempt.md`` for the full minute-by-minute
walkthrough and assertion rationale (SPEC §8.6.3).

This test runs against a deployed test harness (`make harness-up` first).
"""

from __future__ import annotations

import pytest

from tests.chaos import framework as fw

pytestmark = pytest.mark.chaos


def test_scenario_12() -> None:
    def setup() -> None:
        fw.reset_orchestrator_state()
        # Mutating: trip the alarm to authorize failover.
        fw.trip_primary_alarm(0.0)

    def assertions() -> dict[str, callable]:
        return {
            "primary_role_passive": lambda: fw.assert_indicator_role(fw.PRIMARY_REGION, "PASSIVE"),
            "secondary_role_active": lambda: fw.assert_indicator_role(
                fw.SECONDARY_REGION, "ACTIVE"
            ),
        }

    def cleanup() -> None:
        fw.reset_orchestrator_state()
        # restore primary alarm to clear so subsequent scenarios start green
        fw.trip_primary_alarm(1.0)

    result = fw.run_scenario(
        name="scenario-12-split-brain-attempt",
        setup=setup,
        wait_seconds=180,
        assertions=assertions,
        cleanup=cleanup,
    )
    assert result.passed, "\n".join(result.failures)
