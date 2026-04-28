# Solution Overview

**Audience:** Engineering leadership, new joiners.

This document is a 5-minute orientation. For component-by-component depth see
[`architecture.md`](architecture.md); for the rule that authorizes a failover
see [`decision-engine.md`](decision-engine.md); for runbooks see
[`../runbooks/`](../runbooks/).

## Problem

A critical ECS Fargate application running multi-region needs to fail over
from `us-east-1` to `us-east-2` (and back) only when independent infrastructure
and data-tier signals prove that moving traffic is safer than staying put.
The system must be **rock-solid against a real region outage** and
**deliberately insensitive** to single-app deploys, 3-minute response gaps,
single-AZ events, transient API Gateway 5xx, and single-signal red flags.

## What we built

A **profile-driven, per-app, multi-region orchestrator** with three layers:

1. **Decision** — A Decision Engine Lambda runs every minute in each region.
   It applies the rule in [`decision-engine.md`](decision-engine.md) §4.2:
   `count(Tier1 red) ≥ tier1_quorum AND duration(red) ≥ dwell AND
   time_since_last_decision ≥ hysteresis AND auto_failover == true`. The
   four-gate check is what makes the orchestrator deliberately slow to act.

2. **Execution** — A Step Functions Standard state machine carries out the
   ordered DNS-first failover (drain primary indicator → flip R53 control
   metric → wait for propagation → promote secondary indicator → operator
   approves Aurora promotion → confirm Aurora writer in target →
   postcheck). Failback mirrors the workflow in reverse, always
   operator-triggered.

3. **Operator interface** — `failoverctl` (a thin boto3 CLI) and direct
   `aws lambda invoke` calls. No API Gateway in front (POC concession;
   JPMC port adds it).

## What it explicitly does NOT do

- Promote Aurora automatically. SPEC §2 #7 + CLAUDE.md §2 #8: every Aurora
  flip is operator-triggered via `SendTaskSuccess` on a paused state.
- Auto-failback. CLAUDE.md §2 #9: even when `auto_failover=true`,
  `auto_failback` stays false. Failback is always a human decision.
- Use DynamoDB at runtime, AppConfig for the regional indicator, or
  Route 53 ARC. The first two are "future migrations" (SPEC §14); the
  third is org-policy-forbidden (SPEC §2 #2).
- Talk to AWS over the public internet. Every Lambda is VPC-attached;
  every boto3 client uses an explicit `endpoint_url=` pointing at an
  in-region VPC interface endpoint (CLAUDE.md §2 #4).

## Reading order

| Read this | Then read | Why |
|---|---|---|
| `solution-overview.md` (here) | `architecture.md` | Components |
| `architecture.md` | `decision-engine.md` | Why a failover authorizes |
| `decision-engine.md` | `operations.md` | Day-to-day |
| `failure-modes.md` | `scenarios/scenario-NN-*.md` | Worked examples |
| `onboarding-new-app.md` | `profile-reference.md` | Add a new app |

## SLO targets

| Target | Value |
|---|---|
| RTO | 15 min from authorization to STABLE_SECONDARY (DNS-first) |
| RPO | 5 min worst-case from Aurora replica lag |
| Decision latency | 1 minute (EventBridge schedule) |
| False-positive failover budget | 0 per quarter (we'd rather miss than over-trip) |

_Last reviewed: 2026-04-27._
