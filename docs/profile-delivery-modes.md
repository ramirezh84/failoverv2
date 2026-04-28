# Profile Delivery: S3 (default) vs Env Var (inline)

**Audience:** Operators choosing how Lambdas receive the profile YAML.

The orchestrator supports two delivery mechanisms for the per-app profile.
Both go through the same parser and validator (`lib/profile_loader.py`);
they differ only in where the YAML text comes from at Lambda invocation time.

## S3 mode (default)

- Lambda env vars: `PROFILE_BUCKET`, `PROFILE_KEY`
- Lambda calls `s3.get_object(...)` on every invocation (no caching)
- Profile changes: upload new YAML to the **primary** profile bucket;
  CRR replicates to secondary; next Lambda tick (~60s) picks it up

## Env-var mode (opt-in)

- Lambda env var: `PROFILE_YAML` contains the entire YAML text
- No runtime S3 dependency for profile loading
- Profile changes: edit local YAML → `make runtime-apply` → Terraform updates
  Lambda config in both regions; next cold start picks up the new value
  (warm Lambdas continue with the old config until they're reused or recycled)

## Tradeoffs

| Concern | S3 mode | Env-var mode |
|---|---|---|
| Runtime S3 dependency | Yes (every invocation) | No |
| Cold start | +1 S3 GET (~50–200ms) | None |
| Profile update propagation | ~60s (CRR + tick) | New cold starts immediately; warm starts on next recycle |
| Profile size | Effectively unlimited | Bound by Lambda env-var budget (4 KB total across all env vars; current profile ~2.4 KB) |
| Cross-region consistency | CRR (eventual, ~60s) | Terraform applies both regions in one run |
| Audit / versioning | S3 versioning + KMS audit | Terraform plan diff + git history |
| Read-access blast radius | S3 IAM + KMS grants | Anyone with `lambda:GetFunctionConfiguration` |
| IAC reproducibility | Profile lives outside IaC (in S3) | Profile lives **in** the IaC plan |
| Suitable for air-gapped accounts | Awkward (still needs S3) | Yes |
| Suitable for compliance accounts that forbid runtime S3 | No | Yes |

## How to switch modes

### S3 → env-var

In `terraform/apps/<app>/shared.tfvars`:

```hcl
profile_yaml_path = "../../../../profiles/<app>.yaml"
```

Then `make runtime-apply`. The Lambda will see `PROFILE_YAML` set and
prefer it over S3. The S3 path remains configured for fallback (in case
you unset `profile_yaml_path` later).

### Env-var → S3

Remove the `profile_yaml_path` line (or set to `""`). Re-apply runtime.
Lambdas will revert to reading from `PROFILE_BUCKET`/`PROFILE_KEY`.

## Behavior contract

The `lib.profile_loader.load_profile()` helper resolves the source per
invocation:

1. If `PROFILE_YAML` env var is set and non-empty → parse it directly.
2. Else if `PROFILE_BUCKET` + `PROFILE_KEY` are set → S3 GetObject + parse.
3. Else raise `ValueError("Profile source not configured...")`.

Both modes use the same JSON Schema + Pydantic validation, so a profile
that passes in S3 mode passes in env-var mode and vice versa.

## When to use which

**Use S3 (default) when:**
- You want to update profiles independently of Lambda deployments
- Profile is large or you anticipate growth (>3 KB of YAML)
- You have a workflow that uploads profiles via CI/CD separately from
  infrastructure changes

**Use env-var (inline) when:**
- The compliance posture forbids S3 reads from production Lambdas
- You want profile changes to flow through the IaC review process
  (pull-request diff shows the profile delta)
- You want to eliminate one runtime AWS dependency from the Lambda hot
  path (cold start time, IAM grants, S3 read quotas)
- The account has restricted S3 access or quotas that make per-invocation
  GetObject undesirable

---

_Last reviewed: 2026-04-28._
