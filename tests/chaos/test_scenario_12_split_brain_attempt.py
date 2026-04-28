"""Scenario 12: Split-brain attempt — second StartExecution with the same
execution name is rejected by Step Functions (ExecutionAlreadyExists).

Per CLAUDE.md §5: "Execution name is the failover_id. This makes Step
Functions reject duplicate triggers automatically." This scenario validates
that idempotency at the SFN layer.

See ``docs/scenarios/scenario-12-split-brain-attempt.md``.
"""

from __future__ import annotations

import contextlib
import json
import uuid

import boto3
import pytest
from botocore.exceptions import ClientError

from tests.chaos import framework as fw

pytestmark = pytest.mark.chaos


def _start_execution(execution_name: str, payload: dict) -> tuple[bool, str]:
    """Returns (succeeded, error_code_or_arn)."""
    session = boto3.Session(profile_name=fw.PROFILE)
    sfn = session.client("stepfunctions", region_name=fw.PRIMARY_REGION)
    sts = session.client("sts", region_name=fw.PRIMARY_REGION)
    account = sts.get_caller_identity()["Account"]
    arn = f"arn:aws:states:{fw.PRIMARY_REGION}:{account}:stateMachine:{fw.APP}-failover"
    try:
        resp = sfn.start_execution(
            stateMachineArn=arn, name=execution_name, input=json.dumps(payload)
        )
        return True, resp["executionArn"]
    except ClientError as exc:
        return False, exc.response["Error"]["Code"]


def test_scenario_12() -> None:
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
        # Unique-per-run execution name so reruns aren't poisoned by leftover
        # executions from a previous run (SFN execution names are immutable
        # for 90 days after completion).
        execution_name = f"scenario-12-{uuid.uuid4().hex[:12]}"
        payload = {
            "failover_id": execution_name,
            "app_name": fw.APP,
            "direction": "failover",
            "source_region": fw.PRIMARY_REGION,
            "target_region": fw.SECONDARY_REGION,
            "operator": "scenario-12",
            "requested_at": "2026-04-28T00:00:00+00:00",
            "dry_run": False,
            "profile_snapshot": {
                "components": {
                    "api_gateway": True,
                    "aurora": False,
                    "elasticache": False,
                    "kafka_consumer": True,
                },
                "aurora_manual_approval_required": False,
                "dns_first_failover": True,
                "drain_seconds": 60,
                "quiesce_seconds": 60,
                "r53_propagation_seconds": 90,
                "aurora_confirm_timeout_minutes": 30,
            },
        }
        state["execution_name"] = execution_name
        state["first"] = _start_execution(execution_name, payload)
        # Same name, same input → SFN returns the same arn (idempotent).
        state["same_input"] = _start_execution(execution_name, payload)
        # Same name, different input → SFN rejects with ExecutionAlreadyExists.
        diff_payload = {**payload, "operator": "scenario-12-conflicting"}
        state["diff_input"] = _start_execution(execution_name, diff_payload)

    def assertions() -> dict[str, callable]:
        return {
            "first_started": lambda: (
                state["first"][0],
                f"first={state['first']}",
            ),
            "same_input_returns_same_arn": lambda: (
                state["same_input"][0] and state["same_input"][1] == state["first"][1],
                f"same_input={state['same_input']} first={state['first']}",
            ),
            "diff_input_rejected_as_duplicate": lambda: (
                not state["diff_input"][0]
                and state["diff_input"][1] == "ExecutionAlreadyExists",
                f"diff_input={state['diff_input']}",
            ),
        }

    def cleanup() -> None:
        try:
            if state.get("first", (False, ""))[0]:
                with contextlib.suppress(TimeoutError):
                    fw.wait_for_sfn_status(
                        state["first"][1],
                        {"SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"},
                        timeout=300,
                    )
        finally:
            if "original_profile" in state:
                fw.restore_profile(state["original_profile"])
            fw.reset_orchestrator_state()
            fw.trip_primary_alarm(1.0)

    result = fw.run_scenario(
        name="scenario-12-split-brain-attempt",
        setup=setup,
        wait_seconds=2,
        assertions=assertions,
        cleanup=cleanup,
    )
    assert result.passed, "\n".join(result.failures)
