from __future__ import annotations

from cli.failoverctl import main


def test_main_exits_with_not_implemented_code() -> None:
    rc = main()
    assert rc == 2
