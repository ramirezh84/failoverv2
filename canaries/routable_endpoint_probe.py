"""Cross-region synthetic canary script.

Runs in CloudWatch Synthetics under runtime ``syn-python-selenium-2.1``. The
canary in ``us-east-2`` probes the ``us-east-1`` routable URL, and vice
versa (CLAUDE.md §11 pitfall #4).

The TARGET_URL and IGNORE_TLS_ERRORS env vars are set by the
orchestrator-runtime Terraform module. POC accepts ``IGNORE_TLS_ERRORS=true``
because the outer NLB uses self-signed certs (SPEC §2.1 POC-A).
"""

from __future__ import annotations

import os
from typing import Any

# These imports come from the Synthetics runtime; they're not present in the
# orchestrator's Python environment but DO exist where the canary runs.
try:
    from aws_synthetics.common import synthetics_logger as logger  # type: ignore[import-not-found]
    from aws_synthetics.selenium import synthetics_webdriver as webdriver  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - only present in canary runtime
    logger = None  # type: ignore[assignment]
    webdriver = None  # type: ignore[assignment]


def _probe_once(url: str, *, ignore_tls_errors: bool) -> dict[str, Any]:
    options = {"args": ["--no-sandbox"]}
    if ignore_tls_errors:
        options["args"].append("--ignore-certificate-errors")
    driver = webdriver.Chrome(chrome_options=options)
    try:
        driver.get(url)
        title = driver.title
        return {"url": url, "title": title, "ok": True}
    finally:
        driver.quit()


def handler(_event: object, _context: object) -> dict[str, Any]:
    """Synthetics entrypoint."""
    url = os.environ["TARGET_URL"]
    ignore_tls = os.environ.get("IGNORE_TLS_ERRORS", "false").lower() == "true"
    if logger:
        logger.info(f"probing {url}; ignore_tls_errors={ignore_tls}")
    return _probe_once(url, ignore_tls_errors=ignore_tls)
