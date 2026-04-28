from __future__ import annotations

import pytest

from cli.failoverctl import _build_parser, _region_suffix


def test_argparser_recognizes_status() -> None:
    parser = _build_parser()
    args = parser.parse_args(["status", "test-app"])
    assert args.cmd == "status"
    assert args.app == "test-app"


def test_argparser_failover_with_flags() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        ["failover", "test-app", "--operator", "ramirezh84", "--dry-run", "--region", "us-east-2"]
    )
    assert args.cmd == "failover"
    assert args.dry_run is True
    assert args.region == "us-east-2"
    assert args.operator == "ramirezh84"


def test_argparser_approve_requires_task_token() -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["approve", "test-app"])


@pytest.mark.parametrize(
    ("region", "expected"),
    [("us-east-1", "use1"), ("us-east-2", "use2"), ("eu-west-1", "euwest1")],
)
def test_region_suffix(region: str, expected: str) -> None:
    assert _region_suffix(region) == expected
