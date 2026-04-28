"""Chaos scenario framework — assertion helpers + result emission.

Per SPEC §8.7.2, every scenario asserts ten classes of behavior. The helpers
below give scenario tests a declarative grammar so each scenario file reads
as a list of assertions rather than boilerplate.

Tests are marked ``@pytest.mark.chaos``. They run against a deployed test
harness (no moto). The framework does NOT deploy infra; ``make harness-up``
must have been called.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import boto3

APP = os.environ.get("CHAOS_APP", "test-app")
PRIMARY_REGION = os.environ.get("CHAOS_PRIMARY_REGION", "us-east-1")
SECONDARY_REGION = os.environ.get("CHAOS_SECONDARY_REGION", "us-east-2")
PROFILE = os.environ.get("AWS_PROFILE", "tbed")

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
RESULTS_DIR.mkdir(exist_ok=True, parents=True)


@dataclass
class ScenarioResult:
    name: str
    setup_seconds: float
    wait_seconds: float
    assertions: list[tuple[str, bool, str]] = field(default_factory=list)
    final_state: dict[str, Any] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures

    def to_json(self) -> str:
        return json.dumps(
            {
                "name": self.name,
                "setup_seconds": self.setup_seconds,
                "wait_seconds": self.wait_seconds,
                "assertions": [
                    {"name": n, "passed": p, "detail": d} for n, p, d in self.assertions
                ],
                "final_state": self.final_state,
                "failures": self.failures,
                "passed": self.passed,
            },
            indent=2,
            default=str,
        )

    def write(self) -> Path:
        path = RESULTS_DIR / f"{self.name}.json"
        path.write_text(self.to_json(), encoding="utf-8")
        return path


def _client(service: str, region: str) -> Any:
    session = boto3.Session(profile_name=PROFILE)
    return session.client(service, region_name=region)


# ---------------------------------------------------------------------------
# Assertion helpers (SPEC §8.7.4 illustrative list)
# ---------------------------------------------------------------------------


def assert_dns_resolves_to(record_name: str, expected_substring: str) -> tuple[bool, str]:
    """Resolve ``record_name`` against the private hosted zone and check the
    resolved target contains ``expected_substring`` (e.g. region tag)."""
    import socket  # noqa: PLC0415 — runtime-only import

    try:
        addr = socket.gethostbyname(record_name)
    except socket.gaierror as exc:
        return False, f"DNS lookup failed: {exc}"
    return expected_substring in addr, f"resolved={addr}"


def assert_indicator_role(region: str, expected: str) -> tuple[bool, str]:
    ssm = _client("ssm", region)
    try:
        v = ssm.get_parameter(Name=f"/failover/{APP}/{region}/role")["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        return False, "indicator parameter not set"
    return v == expected, f"got={v}"


def assert_state_machine_path(execution_arn: str, expected: list[str]) -> tuple[bool, str]:
    """Check the ordered list of state names entered matches ``expected``."""
    sfn = _client("stepfunctions", PRIMARY_REGION)
    history = sfn.get_execution_history(executionArn=execution_arn, maxResults=1000)
    states = [
        e["stateEnteredEventDetails"]["name"]
        for e in history["events"]
        if e["type"] == "TaskStateEntered"
        or e["type"] == "PassStateEntered"
        or e["type"] == "WaitStateEntered"
        or e["type"] == "ChoiceStateEntered"
        or e["type"] == "SucceedStateEntered"
    ]
    return states == expected, f"got={states}"


def assert_sns_events_in_order(sqs_queue_url: str, expected_events: list[str]) -> tuple[bool, str]:
    """Drain the test SQS queue subscribed to the SNS topic and check the
    sequence of events. Each scenario uses a fresh test queue."""
    sqs = _client("sqs", PRIMARY_REGION)
    seen: list[str] = []
    end = time.time() + 30
    while time.time() < end:
        resp = sqs.receive_message(
            QueueUrl=sqs_queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=2
        )
        for msg in resp.get("Messages", []):
            body = json.loads(msg["Body"])
            attrs = body.get("MessageAttributes", {})
            event = attrs.get("event", {}).get("Value", "")
            if event:
                seen.append(event)
            sqs.delete_message(QueueUrl=sqs_queue_url, ReceiptHandle=msg["ReceiptHandle"])
        if len(seen) >= len(expected_events):
            break
    return seen == expected_events, f"got={seen}"


def assert_log_event_count(
    log_group: str, event_name: str, since: datetime, expected_count: int
) -> tuple[bool, str]:
    logs = _client("logs", PRIMARY_REGION)
    query = f'fields @timestamp, @message | filter event = "{event_name}" | stats count() as c'
    start_id = logs.start_query(
        logGroupName=log_group,
        startTime=int(since.timestamp()),
        endTime=int(time.time()),
        queryString=query,
    )["queryId"]
    end = time.time() + 30
    while time.time() < end:
        r = logs.get_query_results(queryId=start_id)
        if r["status"] in {"Complete", "Cancelled", "Failed"}:
            count = int(r["results"][0][0]["value"]) if r["results"] else 0
            return count == expected_count, f"got={count}"
        time.sleep(2)
    return False, "log insights query timed out"


def assert_metric_max(
    namespace: str,
    metric_name: str,
    region: str,
    dimensions: list[dict[str, str]],
    expected_max: float,
    minutes: int = 10,
) -> tuple[bool, str]:
    cw = _client("cloudwatch", region)
    end = datetime.now(UTC)
    start = end - timedelta(minutes=minutes)
    resp = cw.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=dimensions,
        StartTime=start,
        EndTime=end,
        Period=60,
        Statistics=["Maximum"],
    )
    points = resp.get("Datapoints", [])
    actual = max((p["Maximum"] for p in points), default=None)
    return actual == expected_max, f"got={actual}"


def assert_alarm_state(alarm_name: str, region: str, expected: str) -> tuple[bool, str]:
    cw = _client("cloudwatch", region)
    resp = cw.describe_alarms(AlarmNames=[alarm_name])
    if not resp["MetricAlarms"]:
        return False, "alarm not found"
    return resp["MetricAlarms"][0]["StateValue"] == expected, (
        f"got={resp['MetricAlarms'][0]['StateValue']}"
    )


def assert_audit_records(bucket: str, prefix: str, min_count: int = 1) -> tuple[bool, str]:
    s3 = _client("s3", PRIMARY_REGION)
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    n = resp.get("KeyCount", 0)
    return n >= min_count, f"count={n}"


def assert_no_failover_started(since_seconds: int = 300) -> tuple[bool, str]:
    """Assert no failover Step Functions execution started in the last N seconds
    in either region. Used by non-mutating scenarios to verify no failover was
    triggered."""
    session = boto3.Session(profile_name=PROFILE)
    sts = session.client("sts", region_name=PRIMARY_REGION)
    account = sts.get_caller_identity()["Account"]
    cutoff = datetime.now(UTC) - timedelta(seconds=since_seconds)
    found: list[str] = []
    for region in (PRIMARY_REGION, SECONDARY_REGION):
        sfn = session.client("stepfunctions", region_name=region)
        for sm in (f"{APP}-failover", f"{APP}-failback"):
            arn = f"arn:aws:states:{region}:{account}:stateMachine:{sm}"
            try:
                resp = sfn.list_executions(stateMachineArn=arn, maxResults=20)
            except sfn.exceptions.StateMachineDoesNotExist:
                continue
            for ex in resp.get("executions", []):
                start = ex["startDate"]
                if start.replace(tzinfo=UTC) >= cutoff:
                    found.append(f"{region}:{sm}:{ex['name']}:{ex['status']}")
    return not found, f"unexpected_executions={found}" if found else "no_executions"


def assert_aurora_writer_in(global_cluster_id: str, expected_region: str) -> tuple[bool, str]:
    rds = _client("rds", PRIMARY_REGION)
    resp = rds.describe_global_clusters(GlobalClusterIdentifier=global_cluster_id)
    members = resp["GlobalClusters"][0].get("GlobalClusterMembers", [])
    for m in members:
        if m.get("IsWriter"):
            arn = m["DBClusterArn"]
            actual = arn.split(":")[3]
            return actual == expected_region, f"writer in {actual}"
    return False, "no writer found"


# ---------------------------------------------------------------------------
# Setup actions (controlled chaos injection)
# ---------------------------------------------------------------------------


def trip_primary_alarm(value: float = 0.0) -> None:
    """Force the PrimaryHealthControl metric to ``value`` (0.0 trips, 1.0 clears)."""
    cw = _client("cloudwatch", PRIMARY_REGION)
    cw.put_metric_data(
        Namespace=f"Failover/{APP}",
        MetricData=[
            {
                "MetricName": "PrimaryHealthControl",
                "Value": value,
                "Unit": "None",
                "Dimensions": [{"Name": "Region", "Value": PRIMARY_REGION}],
                "Timestamp": datetime.now(UTC),
            }
        ],
    )


def force_signal_red(signal_name: str, value: float = 1.0) -> None:
    """Inject a Tier 1 signal value via the orchestrator's metric namespace.
    Used by scenarios to simulate red conditions without touching real infra."""
    cw = _client("cloudwatch", PRIMARY_REGION)
    cw.put_metric_data(
        Namespace=f"Failover/{APP}/Signals",
        MetricData=[
            {
                "MetricName": signal_name,
                "Value": value,
                "Unit": "Count",
                "Dimensions": [
                    {"Name": "Region", "Value": PRIMARY_REGION},
                    {"Name": "Tier", "Value": "1"},
                ],
                "Timestamp": datetime.now(UTC),
            }
        ],
    )


def reset_orchestrator_state() -> None:
    """Equivalent to `make scenario-reset`. Called in scenario fixtures."""
    import subprocess  # noqa: PLC0415

    subprocess.run(  # noqa: S603 — chaos framework runs vetted local scripts
        ["bash", "scripts/scenario_reset.sh", APP, PRIMARY_REGION, SECONDARY_REGION],  # noqa: S607
        check=True,
    )


# ---------------------------------------------------------------------------
# Scenario harness
# ---------------------------------------------------------------------------


def run_scenario(
    name: str,
    *,
    setup: callable,
    wait_seconds: int,
    assertions: callable,
    cleanup: callable | None = None,
) -> ScenarioResult:
    """Run one scenario end-to-end.

    Per SPEC §8.7.2: setup → wait → evaluate every assertion → cleanup.
    Cleanup runs even if assertions fail (failback paths are themselves
    tested).
    """
    result = ScenarioResult(name=name, setup_seconds=0.0, wait_seconds=0.0)
    t0 = time.time()
    try:
        setup()
        result.setup_seconds = time.time() - t0
        t1 = time.time()
        time.sleep(wait_seconds)
        result.wait_seconds = time.time() - t1
        for assertion_name, fn in assertions().items():
            ok, detail = fn()
            result.assertions.append((assertion_name, ok, detail))
            if not ok:
                result.failures.append(f"{assertion_name}: {detail}")
    finally:
        if cleanup is not None:
            try:
                cleanup()
            except Exception as exc:
                result.failures.append(f"cleanup_failed: {exc}")
    result.write()
    return result


__all__ = [
    "APP",
    "PRIMARY_REGION",
    "RESULTS_DIR",
    "SECONDARY_REGION",
    "ScenarioResult",
    "assert_alarm_state",
    "assert_audit_records",
    "assert_aurora_writer_in",
    "assert_dns_resolves_to",
    "assert_indicator_role",
    "assert_log_event_count",
    "assert_metric_max",
    "assert_no_failover_started",
    "assert_sns_events_in_order",
    "assert_state_machine_path",
    "force_signal_red",
    "reset_orchestrator_state",
    "run_scenario",
    "trip_primary_alarm",
]
