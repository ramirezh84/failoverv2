# Split-brain recovery

**Audience:** SRE on-call.

## When to use

`failoverctl status test-app` shows BOTH regions with role=ACTIVE.

## Prerequisites

- AWS profile `tbed`. The orchestrator's anti-split-brain guard should prevent this; if you're here, something is very wrong.

## Procedure

1. STOP. Do not let the app continue writing in both regions.
2. Determine which region you want to keep ACTIVE. Usually that's the region holding the Aurora writer (check RDS console).
3. In the OTHER region, manually set the indicator to PASSIVE: `failoverctl drain test-app --region <other-region> --operator $USER`. (This sets DRAINING; after drain_seconds, follow up with another invocation that sets PASSIVE — until then the app's Kafka consumer pauses.)
4. Verify: `failoverctl status test-app` shows exactly one ACTIVE.
5. File a bug — split-brain occurring at all is a defect.

## Verification

- Exactly one region with role=ACTIVE.
- DNS resolves to the same region.
- Aurora writer in the same region.

## Rollback

_(none)_

## Escalation

- Page Principal Engineer immediately. This is a P0.

_Last reviewed: 2026-04-27._
