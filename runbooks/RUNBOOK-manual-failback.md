# Manual failback

**Audience:** SRE on-call.

## When to use

Primary region has been stable for `stable_minutes_before_failback` (default 30 min) and you want to return traffic.

## Prerequisites

- AWS profile `tbed` exported.
- Primary region Tier 1 signals all green for ≥30 min (check dashboard).
- Aurora primary cluster reachable (RDS console).
- Primary ECS service has running task count >= 1.

## Procedure

1. Confirm current state: `failoverctl status test-app`. Secondary should be ACTIVE.
2. Trigger failback: `failoverctl failback test-app --operator $USER`.
3. When `aurora_gate_paused` SNS fires, follow `RUNBOOK-aurora-promotion.md` (this time promoting the primary cluster to writer).
4. Approve: `failoverctl approve test-app --task-token <token> --reason 'Aurora promoted to primary by $USER'`.
5. Wait for `failback_completed`.

## Verification

- DNS resolves to primary outer NLB.
- Aurora writer in primary region.
- Primary indicator ACTIVE; secondary PASSIVE.

## Rollback

- If primary degrades during failback, the state machine routes to FAIL. Re-run failover.

## Escalation

- Same as `RUNBOOK-manual-failover.md`.

_Last reviewed: 2026-04-27._
