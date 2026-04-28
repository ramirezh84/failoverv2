# ADR 0002 — SSM Parameter Store + S3 (not DynamoDB) for runtime state

**Status:** Accepted
**Date:** 2026-04-27
**Deciders:** Principal Engineer

## Context

Runtime state for the orchestrator needs to persist between Lambda
invocations: the latest decision, the current regional indicator, the
in-flight failover id. DynamoDB is the obvious choice, and DynamoDB
Global Tables would handle the cross-region story for free.

## Decision

For the POC, runtime state lives in **SSM Parameter Store + S3 with
CRR** only. No DynamoDB at runtime. The `lib/state_store.py` interface
is the single isolation point so that a future swap to DynamoDB Global
Tables (SPEC §14) is a localized change.

## Consequences

**Positive:**
- Conforms to org policy at the time of build (SPEC §2 #3).
- SSM has the per-region locality we need for free; S3 CRR carries the
  audit trail across regions.
- One less AWS service to authorize and observe.

**Negative:**
- Multi-write contention is harder than DDB conditional writes. We
  mitigate by keeping writes per-region and using executor sequence
  numbers as the anti-split-brain guard.
- SSM Parameter Store throttling is real at high write rates; the
  orchestrator's write rate is low (<1/min/region) so this is fine.

## Alternatives Considered

- **DynamoDB Global Tables:** Forbidden at build time. Future migration.
- **S3-only state:** Rejected — S3 has eventually-consistent reads in
  some failure scenarios; SSM gives us read-after-write consistency
  per-region.
- **In-memory state:** Rejected — Lambda invocations don't share memory
  reliably; cold starts lose state.
