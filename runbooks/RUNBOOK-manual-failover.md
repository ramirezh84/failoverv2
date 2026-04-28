# Manual failover

**Audience:** SRE on-call.

## When to use

You need to trigger a failover by hand. Either Decision Engine fired SNS HIGH (auto_failover=false) or you have out-of-band evidence that a failover is required.

## Prerequisites

- AWS profile `tbed` exported and authenticated.
- `failoverctl` on PATH (from `pyproject.toml` script).
- You know the target region (usually `us-east-2` from `us-east-1`).
- Aurora secondary cluster is up (RDS console).
- Secondary ECS service has running task count >= 1.

## Procedure

1. Confirm current state: `failoverctl status test-app`. Verify primary indicator is ACTIVE and decision_state.
2. Trigger failover: `failoverctl failover test-app --operator $USER`. Capture the `execution_arn` in the response.
3. Watch progress: `failoverctl history test-app` or Step Functions console.
4. When SNS sends `aurora_gate_paused`, follow `RUNBOOK-aurora-promotion.md`.
5. After Aurora promotion, approve: `failoverctl approve test-app --task-token <token-from-sns> --reason 'Aurora promoted by $USER'`.
6. Wait for `failover_completed` SNS. Verify with `failoverctl status test-app`: secondary role=ACTIVE, primary role=PASSIVE, decision_state.state=STABLE_SECONDARY.

## Verification

- DNS resolves to secondary's outer NLB.
- App's `/health` (via secondary endpoint) returns 200.
- Aurora writer is in secondary region (RDS console).
- Synthetic canary in opposite region (us-east-1) reports failures (expected — primary is now passive).
- S3 audit bucket has fresh `executor-runs/<failover-id>.json`.

## Rollback

- If failover went bad mid-flight, do NOT race the state machine. It will route to FAIL on its own.
- If failover completed but app is unhealthy, follow `RUNBOOK-manual-failback.md` to return to primary.

## Escalation

- If state machine stuck > 30 min: `RUNBOOK-stuck-state-machine.md`.
- If both regions show ACTIVE: `RUNBOOK-split-brain-recovery.md`.
- Page primary on-call.

_Last reviewed: 2026-04-27._
