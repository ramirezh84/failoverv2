# Onboarding a New App

**Audience:** Engineer adding a new ECS Fargate app to the orchestrator.

The orchestrator is profile-driven (CLAUDE.md §1). Onboarding is a profile
change + a Terraform stack copy + a deploy. No code change required.

## 1. Open an issue

Use the `new_app_onboarding` issue template under [`.github/ISSUE_TEMPLATE/`](../.github/ISSUE_TEMPLATE/).
Fill in the network ARNs, regions, components, and SLOs.

## 2. Author the profile

Copy `profiles/test-app.yaml` to `profiles/<your-app>.yaml`. Replace the
ARNs and IDs with your app's actual values. Reference fields against
[`profile-reference.md`](profile-reference.md) (auto-generated from
`profile.schema.json`).

For the **first 30 days** of a new app:
- `failover.auto_failover: false` — alert-only.
- `aurora.manual_approval_required: true` (default).
- `aurora.dns_first_failover: true` (default for read-tolerant apps).

## 3. Validate the profile locally

```bash
uv run python scripts/validate_profiles.py
```

CI runs the same check. A profile that fails schema validation cannot land
on `main`.

## 4. Add the Terraform stack

```bash
cp -R terraform/apps/test-app terraform/apps/<your-app>
sed -i '' 's|test-app|<your-app>|g' terraform/apps/<your-app>/shared.tfvars
sed -i '' 's|test-app|<your-app>|g' terraform/apps/<your-app>/base/backend.tf
sed -i '' 's|test-app|<your-app>|g' terraform/apps/<your-app>/runtime/backend.tf
```

CI's `terraform-validate` step runs `terraform validate` for the new root
module — ensure it passes locally first:

```bash
cd terraform/apps/<your-app>/base && terraform init -backend=false && terraform validate
cd ../runtime && terraform init -backend=false && terraform validate
```

## 5. CI

Open a PR. The CI jobs that gate landing:
- `lint-python`, `unit-tests`, `mypy strict`
- `profile-schema-validation`
- `terraform-fmt`, `terraform-validate`, `tflint`, `checkov`
- `iam-policy-check`, `vpc-endpoint-check`, `boto3-endpoint-check`

Self-merge after green per CLAUDE.md §1.1 velocity mode.

## 6. Deploy

Manual local apply, profile `tbed`:

```bash
export AWS_PROFILE=tbed
make harness-up APP=<your-app>
```

The base layer (Aurora, VPCs, NLBs) takes 15–25 minutes the first time.
Runtime layer takes <5 minutes. Subsequent runtime-only changes:

```bash
make runtime-apply APP=<your-app>
```

## 7. Post-deploy verification

```bash
failoverctl status <your-app>
make scenario-1 APP=<your-app>   # signal_collector + decision_engine wired
make scenario-7 APP=<your-app>   # dry-run completes end-to-end
```

If both scenarios pass, the app is onboarded.

## 8. Stage 1 → Stage 2 promotion

After 30 days of successful Stage 1 (alert-only) operation, you may flip
`auto_failover: true` via a profile change PR. Tier1 quorum and dwell
should already be tuned based on the first month's signal patterns.

## 9. What you don't have to do

- No code change in `lambdas/`, `lib/`, or `statemachines/`. The
  orchestrator's behavior is entirely profile-driven.
- No new IAM roles by hand — `terraform/modules/orchestrator-runtime/iam.tf`
  scopes per-app automatically.
- No new SNS topic — the account-level topic is reused; subscribers
  filter by `app_name` message attribute (SPEC §2 #15).

_Last reviewed: 2026-04-27._
