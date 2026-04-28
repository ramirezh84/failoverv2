# Security Policy

## Reporting a vulnerability

This is a private POC repository owned by the Principal Engineer. Report any
suspected vulnerability privately to the repository owner via direct message
or email. Do not open a public issue describing exploit details.

## Supported versions

Only the `main` branch is supported.

## Dependency-update cadence

- Dependabot is enabled for security updates only.
- Quarterly cadence for non-security dependency upgrades, performed under
  the regular PR + CI flow.

## Known POC concessions

The POC accepts the following risks that are reverted on the JPMC port:

- Self-signed TLS certificates at the outer NLB; the synthetic canary runs
  with `ignoreHttpsErrors: true` (see `SPEC.md` §2.1 POC-A).
- AWS profile `tbed` has admin in the personal account; CLI uses static
  credentials rather than federated SSO.
- Single-account deployment (JPMC will use multi-account workspaces).
- No external change-management ticket integration.

These are listed in [`SPEC.md`](SPEC.md) §2.1 and revert items in §14.
