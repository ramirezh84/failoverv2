# ADR 0004 — Step Functions Standard for orchestration

**Status:** Accepted
**Date:** 2026-04-27
**Deciders:** Principal Engineer

## Context

The failover workflow is a multi-step orchestration with manual approval
gates, idempotent re-entry on Lambda crash, and audit retention. We
considered building this in a single long-running Lambda or in
EventBridge-chained Lambdas.

## Decision

Use **Step Functions Standard** workflows. Specifically:

- `failover.asl.json` and `failback.asl.json` definitions live in
  `statemachines/` as JSON; Terraform `templatefile()` injects Lambda ARNs.
- `waitForTaskToken` integration with SNS for the Aurora approval gate.
- Per-state `Retry`/`Catch` for transient AWS failures.
- Standard (not Express) — Express does not support `waitForTaskToken`.

## Consequences

**Positive:**
- Pause indefinitely for manual approval — Lambda's 15-min cap is
  irrelevant.
- Idempotent re-entry on Lambda crash mid-flight is native.
- 90-day execution history for free; every transition logged.
- `Retry`/`Catch` declaratively reduces boilerplate.

**Negative:**
- Cost is small but non-zero (~$0.025 per 1000 transitions; expected
  rate <100 transitions per execution × <10 executions per app per year =
  pocket change).
- ASL JSON is a DSL with its own quirks (see `${...}` vs `$.x` collision
  noted in CHANGELOG).

**Neutral:**
- Standard (not Express) means we can't use Express's higher rate, but
  the orchestrator's rate is naturally low.

## Alternatives Considered

- **Single long-running Lambda:** Rejected — 15-min cap forbids the
  Aurora approval gate.
- **EventBridge-chained Lambdas with state in SSM:** Rejected — re-implements
  Step Functions; every action would need its own idempotency, ordering,
  and crash-resume logic.
- **AWS SWF:** Legacy; Step Functions is the supported successor.
