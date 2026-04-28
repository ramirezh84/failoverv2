"""Scenario 04: Full primary region outage → operator triggers failover.

Auto_failover is off (per test-app profile); operator manually triggers a
failover. We override the profile to disable the aurora component so the
state machine flows DNS → indicator → POSTCHECK → COMPLETED end-to-end
without requiring a real Aurora promotion (covered separately in scenario 8).

See ``docs/scenarios/scenario-04-full-region-outage.md``.
"""

from __future__ import annotations

import pytest

from tests.chaos import framework as fw

pytestmark = pytest.mark.chaos


def test_scenario_04() -> None:
    state: dict = {}

    def setup() -> None:
        fw.reset_orchestrator_state()
        # Override profile to skip Aurora orchestration for this scenario.
        state["original_profile"] = fw.patch_profile(
            {
                "components": {"aurora": False},
                "aurora": None,
                "failover": {"auto_failover": False},
            }
        )
        # Trip the alarm so SREs see the alert (does not auto-trigger).
        fw.trip_primary_alarm(0.0)
        # Operator decides to fail over.
        invoke = fw.invoke_manual_trigger("failover", operator="scenario-04")
        assert invoke.get("ok"), f"manual_trigger failed: {invoke}"
        state["execution_arn"] = invoke["execution_arn"]
        # Wait for SFN to finish.
        state["status"] = fw.wait_for_sfn_status(
            state["execution_arn"], {"SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"}, timeout=300
        )

    def assertions() -> dict[str, callable]:
        return {
            "sfn_succeeded": lambda: (
                state.get("status") == "SUCCEEDED",
                f"status={state.get('status')}",
            ),
            "primary_role_passive": lambda: fw.assert_indicator_role(fw.PRIMARY_REGION, "PASSIVE"),
            "secondary_role_active": lambda: fw.assert_indicator_role(
                fw.SECONDARY_REGION, "ACTIVE"
            ),
        }

    def cleanup() -> None:
        try:
            if "original_profile" in state:
                fw.restore_profile(state["original_profile"])
        finally:
            fw.reset_orchestrator_state()
            fw.trip_primary_alarm(1.0)

    result = fw.run_scenario(
        name="scenario-04-full-region-outage",
        setup=setup,
        wait_seconds=10,
        assertions=assertions,
        cleanup=cleanup,
    )
    assert result.passed, "\n".join(result.failures)
