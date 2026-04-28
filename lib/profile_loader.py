"""Profile loader and validator.

Single entrypoint for reading per-app profiles. SPEC §7 + CLAUDE.md §6:
business logic must never read a profile directly from S3; this module is the
only place that imports the schema, parses YAML, validates, and returns a
typed object.

Returns a ``Profile`` Pydantic model; all callers consume the model, not raw
dicts. Pydantic v2 is used.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from lib.aws_clients import s3

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "profiles" / "profile.schema.json"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Components(_Strict):
    api_gateway: bool
    aurora: bool
    elasticache: bool
    kafka_consumer: bool


class Network(_Strict):
    outer_nlb_arn_primary: Annotated[str, Field(pattern=r"^arn:aws:elasticloadbalancing:")]
    outer_nlb_arn_secondary: Annotated[str, Field(pattern=r"^arn:aws:elasticloadbalancing:")]
    alb_arn_primary: Annotated[str, Field(pattern=r"^arn:aws:elasticloadbalancing:")]
    alb_arn_secondary: Annotated[str, Field(pattern=r"^arn:aws:elasticloadbalancing:")]
    api_gw_id_primary: str | None = None
    api_gw_id_secondary: str | None = None
    routable_url_primary: Annotated[str, Field(pattern=r"^https://")]
    routable_url_secondary: Annotated[str, Field(pattern=r"^https://")]


class Dns(_Strict):
    global_record_name: Annotated[str, Field(min_length=4)]
    hosted_zone_id: Annotated[str, Field(pattern=r"^Z[A-Z0-9]{1,32}$")]


class Aurora(_Strict):
    cluster_id_primary: str
    cluster_id_secondary: str
    global_cluster_id: str
    writer_policy: Literal["pin_primary", "follow_traffic"]
    manual_approval_required: bool
    aurora_confirm_timeout_minutes: Annotated[int, Field(ge=1, le=240)]
    dns_first_failover: bool


class Elasticache(_Strict):
    global_replication_group_id: str
    auto_failover: bool = False


class Kafka(_Strict):
    consumer_group: str
    gate_on_indicator: bool


class Signals(_Strict):
    tier1_quorum: Annotated[int, Field(ge=1, le=10)]
    dwell_minutes: Annotated[int, Field(ge=1, le=60)]
    hysteresis_minutes: Annotated[int, Field(ge=0, le=60)]
    canary_failure_rate_pct: Annotated[int, Field(ge=1, le=100)]


class Canary(_Strict):
    ignore_tls_errors: bool
    internal_ca_bundle_s3_uri: str | None


class Failover(_Strict):
    auto_failover: bool
    auto_failback: Literal[False]  # CLAUDE.md §2 hard constraint #9
    drain_seconds: Annotated[int, Field(ge=10, le=600)]
    quiesce_seconds: Annotated[int, Field(ge=10, le=600)]
    r53_propagation_seconds: Annotated[int, Field(ge=30, le=600)]
    stable_minutes_before_failback: Annotated[int, Field(ge=5, le=1440)]


class Slo(_Strict):
    rto_minutes: Annotated[int, Field(ge=1, le=240)]
    rpo_minutes: Annotated[int, Field(ge=0, le=240)]


EventName = Literal[
    "failover_authorized",
    "failover_initiated",
    "failover_step_completed",
    "failover_completed",
    "failover_failed",
    "failback_initiated",
    "failback_completed",
    "failback_failed",
    "signal_red",
    "signal_recovered",
]


class Notifications(_Strict):
    sns_topic_arn_primary: Annotated[str, Field(pattern=r"^arn:aws:sns:")]
    sns_topic_arn_secondary: Annotated[str, Field(pattern=r"^arn:aws:sns:")]
    events: Annotated[list[EventName], Field(min_length=1)]


_REGIONS = ("us-east-1", "us-east-2")


class Profile(_Strict):
    app_name: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{2,62}$")]
    pattern: Literal["active_passive", "active_active"]
    primary_region: Literal["us-east-1", "us-east-2"]
    secondary_region: Literal["us-east-1", "us-east-2"]
    components: Components
    network: Network
    dns: Dns
    aurora: Aurora | None
    elasticache: Elasticache | None
    kafka: Kafka
    signals: Signals
    canary: Canary
    failover: Failover
    slo: Slo
    notifications: Notifications

    @field_validator("secondary_region")
    @classmethod
    def _regions_differ(cls, v: str, info: Any) -> str:
        primary = info.data.get("primary_region")
        if primary == v:
            raise ValueError("secondary_region must differ from primary_region")
        return v

    @model_validator(mode="after")
    def _cross_field_consistency(self) -> Profile:
        if self.components.aurora and self.aurora is None:
            raise ValueError("components.aurora=true requires the aurora block")
        if not self.components.aurora and self.aurora is not None:
            raise ValueError("components.aurora=false requires aurora=null")
        if self.components.elasticache and self.elasticache is None:
            raise ValueError("components.elasticache=true requires the elasticache block")
        if not self.components.elasticache and self.elasticache is not None:
            raise ValueError("components.elasticache=false requires elasticache=null")
        if self.components.api_gateway and not (
            self.network.api_gw_id_primary and self.network.api_gw_id_secondary
        ):
            raise ValueError(
                "components.api_gateway=true requires non-null network.api_gw_id_primary "
                "and network.api_gw_id_secondary"
            )
        return self


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _validate_against_schema(doc: object) -> None:
    """Run JSON-schema validation; raise ``ValueError`` listing every error."""
    validator = Draft202012Validator(_schema())
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    if errors:
        msgs = [
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors
        ]
        raise ValueError("Profile schema validation failed:\n  " + "\n  ".join(msgs))


def parse(yaml_text: str) -> Profile:
    """Parse and validate a YAML profile string."""
    raw = yaml.safe_load(yaml_text)
    if not isinstance(raw, dict):
        raise ValueError("Profile root must be a YAML mapping")  # noqa: TRY004 — domain-level error
    _validate_against_schema(raw)
    return Profile.model_validate(raw)


def load_from_path(path: Path | str) -> Profile:
    """Read and parse a profile from a local filesystem path."""
    text = Path(path).read_text(encoding="utf-8")
    return parse(text)


def load_from_s3(bucket: str, key: str) -> Profile:
    """Read and parse a profile from S3 via the in-region VPC endpoint.

    Always re-reads (no caching). The Decision Engine polls the profile every
    minute, so callers should not memoize across invocations of a Lambda.
    """
    obj = s3().get_object(Bucket=bucket, Key=key)
    body: bytes = obj["Body"].read()
    return parse(body.decode("utf-8"))


__all__ = [
    "Aurora",
    "Canary",
    "Components",
    "Dns",
    "Elasticache",
    "EventName",
    "Failover",
    "Kafka",
    "Network",
    "Notifications",
    "Profile",
    "Signals",
    "Slo",
    "load_from_path",
    "load_from_s3",
    "parse",
]
