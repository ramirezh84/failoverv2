<!--
SPEC.md §11.4 / CONTRIBUTING.md — every section is required.
PRs that omit sections will be returned. Self-merge after CI passes (POC §11.4).
-->

## Linked issue / ADR

Closes #

## What changed

<!-- Bullet the user-visible change. Keep to <=5 lines. -->

## Why

<!-- One sentence: the motivation. Link to ADR if there's an architecture call. -->

## Blast radius

<!-- Which Lambdas / Step Functions states / Terraform modules / profiles are touched? -->

## Manual deploy steps

<!-- If this needs `terraform apply` against a specific module, list the exact commands. -->

```sh
# example
export AWS_PROFILE=tbed
cd terraform/apps/test-app/runtime && terraform apply
```

## Tests

- [ ] Unit tests added / updated
- [ ] Coverage did not decrease
- [ ] Profile schema validation still passes (if profile or schema touched)
- [ ] Terraform `validate` clean (if Terraform touched)

## Documentation

- [ ] Relevant doc(s) in `docs/` updated
- [ ] Relevant runbook(s) in `runbooks/` updated (or N/A)
- [ ] `CHANGELOG.md` entry under `## [Unreleased]`
- [ ] Diagrams regenerated (if architecture touched)

## Self-verification (CLAUDE.md §8)

- [ ] `ruff check` / `ruff format --check` clean
- [ ] `mypy --strict` clean
- [ ] `pytest --cov` clean (≥80% line, ≥70% branch)
- [ ] `terraform fmt -check -recursive` / `terraform validate` clean
- [ ] No IAM `*` actions, no `Resource: "*"`
- [ ] Every boto3 client has explicit `endpoint_url=`
- [ ] No `time.sleep` in any Lambda
