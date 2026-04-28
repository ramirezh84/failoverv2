# Aurora promotion (operator-only)

**Audience:** SRE on-call.

## When to use

Step Functions has paused at AURORA_GATE_PAUSE and SNS sent `aurora_gate_paused` with a task token.

## Prerequisites

- AWS profile `tbed`.
- RDS console open in the **target** region.
- Task token from the SNS message saved.

## Procedure

1. In RDS console, navigate to the global cluster `<app>-global`.
2. Identify the secondary cluster (`<app>-use2` for forward failover; `<app>-use1` for failback).
3. Click 'Failover' (Aurora Global). Confirm. AWS detaches the secondary from the global cluster and promotes its writer.
4. Wait until the secondary cluster status returns to 'available' and shows the writer endpoint.
5. Verify with: `aws --profile tbed --region <target> rds describe-db-clusters --db-cluster-identifier <app>-use2 --query 'DBClusters[0].{Status:Status,Writer:DBClusterMembers[?IsClusterWriter].DBInstanceIdentifier}'`
6. Call `failoverctl approve` with the task token (or `abort` with reason if the promotion failed).

## Verification

- AURORA_CONFIRM_LOOP advances; SNS fires `aurora_writer_confirmed` then `failover_step_completed`.
- Within 30s, the executor moves to POSTCHECK.

## Rollback

- If you accidentally promoted the wrong cluster: call `failoverctl abort --reason 'wrong cluster'` to fail the state machine; then page Principal Engineer.

## Escalation

- Aurora cluster health issues: AWS Support.
- Promotion API errors: paste the AWS console error verbatim into the incident channel.

_Last reviewed: 2026-04-27._
