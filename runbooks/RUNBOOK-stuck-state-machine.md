# Stuck state machine

**Audience:** SRE on-call.

## When to use

A Step Functions execution has been RUNNING for more than its expected duration (typical failover < 10 min including Aurora).

## Prerequisites

- AWS profile `tbed`.

## Procedure

1. Get the execution ARN: `failoverctl history test-app | head`.
2. Check current state: `aws stepfunctions describe-execution --execution-arn <arn>`.
3. Get full history: `aws stepfunctions get-execution-history --execution-arn <arn> --max-results 50`.
4. Identify the state where it stopped advancing.
5. If at AURORA_GATE_PAUSE, the SNS message with the task token is in CW Logs `/aws/states/<app>-failover-use1`. Re-publish or call `failoverctl approve` / `abort`.
6. If at AURORA_CONFIRM_LOOP, check RDS console — Aurora may be promoting slowly.
7. If at WAIT_R53_PROPAGATION, this is normal for up to 90s.
8. If a Lambda raised an exception, the Catch routed to FAIL. Read the exception in the execution history.

## Verification

- Execution status moves out of RUNNING.

## Rollback

- Stop the execution: `aws stepfunctions stop-execution --execution-arn <arn> --error 'OperatorAbort' --cause 'reason'`.
- Then trigger a fresh failover/failback as needed.

## Escalation

- Page Principal Engineer.

_Last reviewed: 2026-04-27._
