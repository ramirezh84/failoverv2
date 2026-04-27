"""Smoke test that anchors the coverage gate while the library is being
filled in. Replaced/extended by real tests in PR #2."""

from __future__ import annotations

import lib


def test_version_is_a_string() -> None:
    assert isinstance(lib.__version__, str)
    assert lib.__version__.count(".") == 2
