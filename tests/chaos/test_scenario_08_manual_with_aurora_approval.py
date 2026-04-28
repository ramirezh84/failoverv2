"""Scenario 08: Manual failover with Aurora manual_approval_required: true. Pauses at Aurora gate; operator approves; full failover then full failback.

See ``docs/scenarios/scenario-08-manual-with-aurora-approval.md`` for the full minute-by-minute
walkthrough and assertion rationale (SPEC §8.6.3).

This test runs against a deployed test harness (`make harness-up` first).
"""

from __future__ import annotations

import pytest

from tests.chaos import framework as fw

pytestmark = pytest.mark.chaos


def test_scenario_08() -> None:
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
        name="scenario-08-manual-with-aurora-approval",
        setup=setup,
        wait_seconds=180,
        assertions=assertions,
        cleanup=cleanup,
    )
    assert result.passed, "\n".join(result.failures)
