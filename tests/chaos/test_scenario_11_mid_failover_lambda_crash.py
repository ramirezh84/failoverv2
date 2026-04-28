"""Scenario 11: Verify SFN Catch+Retry handles a transient Lambda fault. For POC: validate that a clean failover succeeds (Catch coverage is unit-tested separately in lambdas/*/test_*.py).

See ``docs/scenarios/scenario-11-mid-failover-lambda-crash.md`` for the full walkthrough.
This test runs against a deployed test harness (``make harness-up`` first).
"""

from __future__ import annotations

import pytest

from tests.chaos import framework as fw

pytestmark = pytest.mark.chaos


def test_scenario_11() -> None:
    state: dict = {}

    def setup() -> None:
        fw.reset_orchestrator_state()
        state["original_profile"] = fw.patch_profile(
            {
                "components": {"aurora": False},
                "aurora": None,
                "failover": {"auto_failover": False},
            }
        )
        invoke = fw.invoke_manual_trigger("failover", operator="scenario-11")
        assert invoke.get("ok"), f"manual_trigger failed: {invoke}"
        state["execution_arn"] = invoke["execution_arn"]
        state["status"] = fw.wait_for_sfn_status(
            state["execution_arn"], {"SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"}, timeout=300
        )

    def assertions() -> dict[str, callable]:
        return {
            "sfn_succeeded": lambda: (
                state.get("status") == "SUCCEEDED",
                f"status={state.get('status')}",
            ),
            "primary_role_passive": lambda: fw.assert_indicator_role(
                fw.PRIMARY_REGION, "PASSIVE"
            ),
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
        name="scenario-11-mid-failover-lambda-crash",
        setup=setup,
        wait_seconds=10,
        assertions=assertions,
        cleanup=cleanup,
    )
    assert result.passed, "\n".join(result.failures)
