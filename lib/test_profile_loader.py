from __future__ import annotations

from pathlib import Path

import pytest

from lib import profile_loader

REPO = Path(__file__).resolve().parent.parent


def test_example_test_app_profile_round_trips() -> None:
    profile = profile_loader.load_from_path(REPO / "profiles" / "test-app.yaml")
    assert profile.app_name == "test-app"
    assert profile.primary_region == "us-east-1"
    assert profile.secondary_region == "us-east-2"
    assert profile.components.aurora is True
    assert profile.aurora is not None
    assert profile.aurora.dns_first_failover is True
    assert profile.failover.auto_failback is False
    assert "failover_authorized" in profile.notifications.events


@pytest.mark.parametrize(
    "fixture_name",
    [
        "missing_app_name.yaml",
        "bad_app_name_pattern.yaml",
        "same_primary_secondary.yaml",
        "auto_failback_true.yaml",
        "aurora_true_but_block_null.yaml",
        "api_gateway_true_but_no_ids.yaml",
        "dwell_out_of_range.yaml",
        "unknown_event.yaml",
        "bad_sns_arn.yaml",
        "extra_top_level_key.yaml",
    ],
)
def test_invalid_fixtures_are_rejected(fixture_name: str) -> None:
    path = REPO / "tests" / "unit" / "profile_validation" / "invalid" / fixture_name
    with pytest.raises(ValueError, match=r"Profile schema validation failed"):
        profile_loader.load_from_path(path)


def test_pydantic_cross_field_validators_fire() -> None:
    """Same primary/secondary region is caught by the Pydantic validator even
    if JSON-schema is bypassed."""
    text = (REPO / "profiles" / "test-app.yaml").read_text(encoding="utf-8")
    bad = text.replace("secondary_region: us-east-2", "secondary_region: us-east-1")
    with pytest.raises(ValueError, match="Profile schema validation failed"):
        profile_loader.parse(bad)


def test_components_aurora_false_with_block_present_rejected() -> None:
    text = (REPO / "profiles" / "test-app.yaml").read_text(encoding="utf-8")
    # Flip components.aurora to false but leave the block present.
    bad = text.replace("aurora: true", "aurora: false", 1)
    with pytest.raises(ValueError, match="aurora"):
        profile_loader.parse(bad)


def test_parse_rejects_yaml_root_that_is_not_mapping() -> None:
    with pytest.raises(ValueError, match="root must be a YAML mapping"):
        profile_loader.parse("- just a list\n")


def test_load_from_s3_routes_through_aws_client(
    monkeypatch: pytest.MonkeyPatch,
    aws_credentials: None,
    vpc_endpoints: None,
) -> None:
    """load_from_s3 reads via the lib.aws_clients.s3 factory."""
    captured: dict[str, object] = {}

    class FakeBody:
        def __init__(self, payload: bytes) -> None:
            self.payload = payload

        def read(self) -> bytes:
            return self.payload

    class FakeS3:
        def get_object(self, **kwargs: str) -> dict[str, object]:
            captured["Bucket"] = kwargs["Bucket"]
            captured["Key"] = kwargs["Key"]
            return {"Body": FakeBody((REPO / "profiles" / "test-app.yaml").read_bytes())}

    fake = FakeS3()
    monkeypatch.setattr(profile_loader, "s3", lambda: fake)
    profile = profile_loader.load_from_s3("audit-bucket", "test-app/profile.yaml")
    assert profile.app_name == "test-app"
    assert captured == {"Bucket": "audit-bucket", "Key": "test-app/profile.yaml"}


def test_load_from_env_round_trips(monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_text = (REPO / "profiles" / "test-app.yaml").read_text(encoding="utf-8")
    monkeypatch.setenv("PROFILE_YAML", yaml_text)
    profile = profile_loader.load_from_env()
    assert profile.app_name == "test-app"


def test_load_from_env_missing_var_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROFILE_YAML", raising=False)
    with pytest.raises(ValueError, match="not set or empty"):
        profile_loader.load_from_env()


def test_load_profile_prefers_env_over_s3(monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_text = (REPO / "profiles" / "test-app.yaml").read_text(encoding="utf-8")
    monkeypatch.setenv("PROFILE_YAML", yaml_text)
    monkeypatch.setenv("PROFILE_BUCKET", "should-not-be-used")
    monkeypatch.setenv("PROFILE_KEY", "should-not-be-used")
    # If S3 path were taken, this would fail because s3() isn't mocked.
    profile = profile_loader.load_profile()
    assert profile.app_name == "test-app"


def test_load_profile_falls_back_to_s3(monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_text = (REPO / "profiles" / "test-app.yaml").read_text(encoding="utf-8")
    monkeypatch.delenv("PROFILE_YAML", raising=False)
    monkeypatch.setenv("PROFILE_BUCKET", "b")
    monkeypatch.setenv("PROFILE_KEY", "k")

    class FakeBody:
        def read(self) -> bytes:
            return yaml_text.encode()

    class FakeS3:
        exceptions = type("E", (), {"NoSuchKey": type("E", (Exception,), {})})

        def get_object(self, Bucket: str, Key: str) -> dict:  # noqa: N803
            return {"Body": FakeBody()}

    fake = FakeS3()
    monkeypatch.setattr(profile_loader, "s3", lambda: fake)
    profile = profile_loader.load_profile()
    assert profile.app_name == "test-app"


def test_load_profile_no_source_configured_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    for v in ("PROFILE_YAML", "PROFILE_BUCKET", "PROFILE_KEY"):
        monkeypatch.delenv(v, raising=False)
    with pytest.raises(ValueError, match="Profile source not configured"):
        profile_loader.load_profile()
