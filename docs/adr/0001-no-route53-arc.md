# ADR 0001 — No Route 53 ARC

**Status:** Accepted
**Date:** 2026-04-27
**Deciders:** Principal Engineer

## Context

Route 53 Application Recovery Controller (ARC) provides routing controls
that look like a natural fit for the orchestrator. We considered using
ARC routing controls instead of CloudWatch metric → alarm → R53 health
check.

## Decision

Use the indirect pattern: orchestrator emits CloudWatch metric →
CloudWatch alarm watches metric → Route 53 health check is bound to the
alarm. The orchestrator never calls `route53` APIs directly.

## Consequences

**Positive:**
- Lambda has no IAM `route53:*` permissions; the R53 control surface is
  a single CW metric.
- R53 API throttling and outages are isolated from orchestrator code.
- The control surface is observable from any CW dashboard.

**Negative:**
- One extra hop (metric → alarm → health check); ~30s latency added.
- Two configurations to keep in sync (alarm threshold + R53 health check
  binding).

**Neutral:**
- Per-app alarms scale linearly with app count; cost is negligible.

## Alternatives Considered

- **Route 53 ARC routing controls:** Forbidden by org policy (SPEC §2 #2).
- **Lambda calls `route53` directly:** Rejected — wider blast radius;
  single point of failure if R53 API throttles; harder to observe from
  the dashboard.
