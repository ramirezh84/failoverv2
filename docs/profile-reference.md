# Profile Reference

**Audience:** Anyone authoring or modifying a per-app failover profile.
**Generated from:** `profiles/profile.schema.json`. Do not edit by hand —
run `uv run python scripts/generate_profile_reference.py > docs/profile-reference.md`.

This document is the field-by-field reference for the per-app YAML profile.
The orchestrator's runtime behavior is entirely driven by these fields; no
code change is required to onboard a new app.

See [`docs/onboarding-new-app.md`](onboarding-new-app.md) for the workflow,
and [`profiles/profile.schema.json`](../profiles/profile.schema.json) for the
machine-readable contract.

_Schema not yet committed; PR #2 will fill this in._
