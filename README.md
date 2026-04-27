# failoverv2 — Multi-Region Failover Orchestrator

Profile-driven, per-app, multi-region failover orchestrator for ECS Fargate
applications on AWS. Fails an application over from `us-east-1` to `us-east-2`
(and back) only when independent infrastructure and data-tier signals prove
that moving traffic is safer than staying put.

This is the POC build, deployed to a personal AWS account via the `tbed` CLI
profile. The eventual production target is JPMC; the POC is a 100% topology
mirror with concessions only around credentials and process. See
[`SPEC.md`](SPEC.md) for the full design and [`CLAUDE.md`](CLAUDE.md) for
build conventions.

## Quick links

- [SPEC.md](SPEC.md) — source of truth for what to build
- [CLAUDE.md](CLAUDE.md) — source of truth for how to build
- [docs/](docs/) — solution overview, architecture, runbooks, scenarios
- [runbooks/](runbooks/) — operator procedures

## Layout

```text
profiles/        # per-app YAML profiles + JSON Schema
lambdas/         # Python 3.14 Lambdas (handler/logic/aws split)
lib/             # shared Python code
statemachines/   # Step Functions ASL JSON
terraform/       # modules + per-app stacks (base + runtime layers)
canaries/        # CloudWatch Synthetics probe scripts
cli/             # failoverctl operator CLI
docs/            # documentation, diagrams, scenario walkthroughs
runbooks/        # operator procedures
tests/           # unit, integration, chaos
```

## Operating the POC

Deploys are manual and local. CI runs code-quality checks only.

```bash
export AWS_PROFILE=tbed
make harness-up        # one-time per session: base + runtime
make scenario-N        # run a single scenario (1-14)
make stable-suite      # run scenarios-all three consecutive times
```

`make harness-down` is reserved for explicit teardown; the harness stays up
between iteration cycles. See [`docs/operations.md`](docs/operations.md) and
the scenario walkthroughs in [`docs/scenarios/`](docs/scenarios/).
