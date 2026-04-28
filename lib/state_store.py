"""Per-region runtime state, backed by SSM Parameter Store + S3.

This is the single isolation point that allows a future swap to DynamoDB
Global Tables without touching business logic. CLAUDE.md §2 hard constraint
#1 + SPEC §3.2.

Data layout:

    /failover/<app>/<region>/decision      (string param)  — current decision
                                              state JSON ({"state": ..., "reason": ..., "ts": ...})
    /failover/<app>/<region>/signals/last  (string param)  — last signal snapshot
    /failover/<app>/<region>/in_flight     (string param)  — failover_id of any in-flight execution

    s3://<audit-bucket>/<app>/<region>/decisions/<utc-iso>.json
    s3://<audit-bucket>/<app>/<region>/observations/<utc-iso>.json
    s3://<audit-bucket>/<app>/<region>/executor-runs/<failover-id>.json

The state store NEVER touches a region other than its own. Cross-region
visibility is via S3 CRR + the SNS event stream (SPEC §3.2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from botocore.exceptions import ClientError

from lib.aws_clients import s3, ssm

DecisionState = Literal[
    "GREEN",
    "WATCHING",
    "FAILOVER_AUTHORIZED",
    "FAILOVER_IN_FLIGHT",
    "STABLE_SECONDARY",
    "FAILBACK_IN_FLIGHT",
]


@dataclass(frozen=True)
class DecisionRecord:
    """A single decision evaluation. Persisted to SSM (latest) and S3 (history)."""

    state: DecisionState
    reason: str
    timestamp: datetime
    tier1_red_signals: tuple[str, ...]
    quorum_held: bool
    dwell_held: bool
    hysteresis_held: bool
    secondary_safe: bool
    profile_version: str
    extra: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(
            {
                "state": self.state,
                "reason": self.reason,
                "timestamp": self.timestamp.replace(tzinfo=UTC).isoformat(),
                "tier1_red_signals": list(self.tier1_red_signals),
                "quorum_held": self.quorum_held,
                "dwell_held": self.dwell_held,
                "hysteresis_held": self.hysteresis_held,
                "secondary_safe": self.secondary_safe,
                "profile_version": self.profile_version,
                "extra": self.extra,
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def from_json(raw: str) -> DecisionRecord:
        d = json.loads(raw)
        return DecisionRecord(
            state=d["state"],
            reason=d["reason"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            tier1_red_signals=tuple(d["tier1_red_signals"]),
            quorum_held=d["quorum_held"],
            dwell_held=d["dwell_held"],
            hysteresis_held=d["hysteresis_held"],
            secondary_safe=d["secondary_safe"],
            profile_version=d["profile_version"],
            extra=d.get("extra", {}),
        )


def _decision_param(app: str, region: str) -> str:
    return f"/failover/{app}/{region}/decision"


def _in_flight_param(app: str, region: str) -> str:
    return f"/failover/{app}/{region}/in_flight"


def _decision_s3_key(app: str, region: str, ts: datetime) -> str:
    iso = ts.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%S-%fZ")
    return f"{app}/{region}/decisions/{iso}.json"


def _observation_s3_key(app: str, region: str, ts: datetime) -> str:
    iso = ts.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%S-%fZ")
    return f"{app}/{region}/observations/{iso}.json"


def _executor_run_s3_key(app: str, region: str, failover_id: str) -> str:
    return f"{app}/{region}/executor-runs/{failover_id}.json"


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def write_decision(
    app: str,
    region: str,
    record: DecisionRecord,
    audit_bucket: str,
) -> None:
    """Write the latest decision to SSM and append to the S3 audit trail.

    Both writes happen; if the SSM write fails, the function raises and the
    S3 write is skipped (SSM is the live state). If S3 fails after a
    successful SSM write, the audit trail loses one entry and the next
    successful write will be unaffected; we surface the error rather than
    silently swallow.
    """
    payload = record.to_json()
    ssm().put_parameter(
        Name=_decision_param(app, region),
        Value=payload,
        Type="String",
        Overwrite=True,
    )
    s3().put_object(
        Bucket=audit_bucket,
        Key=_decision_s3_key(app, region, record.timestamp),
        Body=payload.encode("utf-8"),
        ContentType="application/json",
    )


def read_latest_decision(app: str, region: str) -> DecisionRecord | None:
    """Return the most recent decision, or ``None`` if no decision exists yet."""
    try:
        resp = ssm().get_parameter(Name=_decision_param(app, region))
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ParameterNotFound":
            return None
        raise
    return DecisionRecord.from_json(resp["Parameter"]["Value"])


def write_observation(
    app: str,
    region: str,
    snapshot: dict[str, Any],
    audit_bucket: str,
    timestamp: datetime,
) -> None:
    """Append a raw signal observation snapshot to the S3 audit trail."""
    body = json.dumps(snapshot, separators=(",", ":"), sort_keys=True, default=str)
    s3().put_object(
        Bucket=audit_bucket,
        Key=_observation_s3_key(app, region, timestamp),
        Body=body.encode("utf-8"),
        ContentType="application/json",
    )


def write_executor_run(
    app: str,
    region: str,
    failover_id: str,
    record: dict[str, Any],
    audit_bucket: str,
) -> None:
    """Write a Step Functions execution record to S3.

    Idempotent: same ``failover_id`` overwrites; combine with Step Functions
    execution-name uniqueness (CLAUDE.md §11 #3) for end-to-end dedupe.
    """
    body = json.dumps(record, separators=(",", ":"), sort_keys=True, default=str)
    s3().put_object(
        Bucket=audit_bucket,
        Key=_executor_run_s3_key(app, region, failover_id),
        Body=body.encode("utf-8"),
        ContentType="application/json",
    )


def claim_in_flight(app: str, region: str, failover_id: str) -> bool:
    """Atomically claim the in-flight slot for ``failover_id``.

    Returns True iff the claim succeeded. Returns False if another
    ``failover_id`` already holds the slot. Implemented by reading the
    parameter (or treating absence as empty), then unconditionally
    overwriting only if the slot is empty or matches ``failover_id`` —
    sufficient under the single-region, single-active-Decision-Engine
    invariant (a region only ever has one Decision Engine running per
    EventBridge tick).
    """
    current = _read_string(app, region, _in_flight_param(app, region))
    if current and current != failover_id:
        return False
    ssm().put_parameter(
        Name=_in_flight_param(app, region),
        Value=failover_id,
        Type="String",
        Overwrite=True,
    )
    return True


def release_in_flight(app: str, region: str) -> None:
    """Release the in-flight slot. Safe to call when nothing is held."""
    try:
        ssm().delete_parameter(Name=_in_flight_param(app, region))
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ParameterNotFound":
            return
        raise


def _read_string(app: str, region: str, name: str) -> str | None:
    """Read a string SSM param; return None if missing."""
    del app, region  # currently unused, retained for future tagging
    try:
        resp = ssm().get_parameter(Name=name)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ParameterNotFound":
            return None
        raise
    return str(resp["Parameter"]["Value"])


__all__ = [
    "DecisionRecord",
    "DecisionState",
    "claim_in_flight",
    "read_latest_decision",
    "release_in_flight",
    "write_decision",
    "write_executor_run",
    "write_observation",
]
