# Glossary

**Audience:** All audiences.

Acronyms and project-specific terms used across SPEC, CLAUDE, docs, and
runbooks.

## Acronyms

| Term | Expansion |
|---|---|
| ASL | Amazon States Language (the JSON DSL Step Functions definitions are written in) |
| CRR | Cross-Region Replication (S3) |
| CW | CloudWatch |
| DDB | DynamoDB (forbidden at runtime per CLAUDE.md §2 #1) |
| HC | Health Check (Route 53) |
| IGW | Internet Gateway |
| KMS | Key Management Service |
| NLB | Network Load Balancer |
| RPO | Recovery Point Objective (max acceptable data loss; we target 5 min) |
| RTO | Recovery Time Objective (max acceptable downtime; we target 15 min) |
| SFN | Step Functions |
| SG | Security Group |
| SLO | Service Level Objective |
| SNS | Simple Notification Service |
| SSM | Systems Manager (Parameter Store) |
| SSE | Server-Side Encryption |
| TLS | Transport Layer Security |
| VPCE | VPC interface endpoint |

## Project-specific terms

| Term | Meaning |
|---|---|
| **Active region** | The region whose `/failover/{app}/{region}/role` parameter is `ACTIVE`. Exactly one region is active at any time. |
| **AURORA_GATE** | The Step Functions state that pauses with `.waitForTaskToken` until an operator approves Aurora promotion. |
| **DNS-first failover** | The default for read-tolerant apps: R53 flips to secondary BEFORE Aurora writer is promoted. SPEC §5.1. |
| **Dwell** | The continuous time the Tier 1 quorum must hold red before authorization. Default 5 min. |
| **failover_id** | Deterministic Step Functions execution name; also the dedupe key for every Lambda invoked by the state machine. CLAUDE.md §11 #3. |
| **Hysteresis** | Minimum time between successive decision changes. Default 3 min. |
| **PrimaryHealthControl** | The CloudWatch metric the orchestrator emits to control the R53 health-check alarm. SPEC §3.2. |
| **Quorum** | The number of distinct Tier 1 signals that must be red to authorize. Default 2. |
| **Regional indicator** | The SSM parameter `/failover/{app}/{region}/role` ∈ {ACTIVE, PASSIVE, DRAINING}. The Kafka consumer gates on this. |
| **Tier 1/2/3** | Signal classification per SPEC §4.1: Tier 1 triggers, Tier 2 gates, Tier 3 informs. |
| **Warm standby** | The secondary region's ECS service runs ≥1 task at all times, ready to receive traffic. SPEC §2 #9. |
| **Writer-first failover** | The legacy variant where Aurora is promoted before R53 flips. Reserved for any future strict-write app. SPEC §5.2. |

## Hard constraint shorthand

When a doc says "POC concession", it refers to one of the items in SPEC
§2.1. When a doc says "JPMC port", it refers to the future migration list
in SPEC §14.

When a doc says "hard constraint", it refers to one of the 10 entries in
CLAUDE.md §2 — these are non-negotiable.

_Last reviewed: 2026-04-27._
