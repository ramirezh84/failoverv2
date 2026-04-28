# Failure Modes

**Audience:** Engineers and SREs.

This is the index. Each scenario has a per-file walkthrough under
[`scenarios/`](scenarios/).

## Scenarios

| # | Title | Walkthrough |
|---|---|---|
| 1 | Deployment 503 blip | [`scenarios/scenario-01-deployment-503-blip.md`](scenarios/scenario-01-deployment-503-blip.md) |
| 2 | ALB unhealthy only | [`scenarios/scenario-02-alb-unhealthy-only.md`](scenarios/scenario-02-alb-unhealthy-only.md) |
| 3 | Single AZ outage | [`scenarios/scenario-03-single-az-outage.md`](scenarios/scenario-03-single-az-outage.md) |
| 4 | Full region outage | [`scenarios/scenario-04-full-region-outage.md`](scenarios/scenario-04-full-region-outage.md) |
| 5 | API GW 5xx storm | [`scenarios/scenario-05-api-gw-5xx-storm.md`](scenarios/scenario-05-api-gw-5xx-storm.md) |
| 6 | App can't reach Aurora | [`scenarios/scenario-06-app-cant-reach-aurora.md`](scenarios/scenario-06-app-cant-reach-aurora.md) |
| 7 | Dry run | [`scenarios/scenario-07-dry-run.md`](scenarios/scenario-07-dry-run.md) |
| 8 | Manual with Aurora approval | [`scenarios/scenario-08-manual-with-aurora-approval.md`](scenarios/scenario-08-manual-with-aurora-approval.md) |
| 9 | Aurora confirmation timeout | [`scenarios/scenario-09-aurora-confirmation-timeout.md`](scenarios/scenario-09-aurora-confirmation-timeout.md) |
| 10 | Failback | [`scenarios/scenario-10-failback.md`](scenarios/scenario-10-failback.md) |
| 11 | Mid-failover Lambda crash | [`scenarios/scenario-11-mid-failover-lambda-crash.md`](scenarios/scenario-11-mid-failover-lambda-crash.md) |
| 12 | Split-brain attempt | [`scenarios/scenario-12-split-brain-attempt.md`](scenarios/scenario-12-split-brain-attempt.md) |
| 13 | Profile change mid-incident | [`scenarios/scenario-13-profile-change-mid-incident.md`](scenarios/scenario-13-profile-change-mid-incident.md) |
| 14 | Canary self-failure | [`scenarios/scenario-14-canary-self-failure.md`](scenarios/scenario-14-canary-self-failure.md) |

## What each scenario proves

- **1, 2, 3, 5, 14**: the orchestrator is *deliberately insensitive* to
  single-component or single-AZ noise.
- **4**: end-to-end failover authorize → execute → Aurora gate →
  postcheck → STABLE_SECONDARY.
- **6**: Tier 1 vs Tier 2 separation: data-tier issues don't trigger
  failover by themselves.
- **7**: dry-run is non-destructive but exercises every state.
- **8, 10**: manual operator workflow including failback.
- **9**: stuck-state-machine handling — system stays in a known state
  rather than trying to roll back DNS to a degraded primary.
- **11**: Step Functions resume-after-crash + Lambda idempotency.
- **12**: split-brain prevention via executor sequence number guard.
- **13**: profile changes propagate within one polling interval.

_Last reviewed: 2026-04-27._
