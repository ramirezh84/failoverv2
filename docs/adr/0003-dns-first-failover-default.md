# ADR 0003 — DNS-first failover is the default

**Status:** Accepted
**Date:** 2026-04-27
**Deciders:** Principal Engineer

## Context

The classical failover ordering is "writer-first": promote Aurora
secondary, confirm writer, then flip DNS. This avoids ANY write failures
during the flip window. But it has two costs:

1. RTO is bounded by Aurora promotion time (typically 1-2 min, can
   be longer under load).
2. If Aurora promotion stalls, R53 stays on the failing primary even
   though reads could already be served from the secondary's replica.

For **read-tolerant apps** (the deposits use case — most reads, occasional
writes that can fail and be retried) DNS-first is strictly better:
RTO is bounded by R53 propagation (~90s), not by Aurora.

## Decision

DNS-first failover (SPEC §5.1) is the default. R53 flips before Aurora
writer promotion; reads are served from the secondary's local Aurora
replica during the gap; writes may fail until Aurora is confirmed in
the new primary, which is the acceptable contract for these apps.

Writer-first (SPEC §5.2) remains a profile flag (`aurora.dns_first_failover: false`)
for any future app that cannot tolerate write failures during the flip
window.

## Consequences

**Positive:**
- Lower RTO for the typical read-heavy app.
- Aurora-confirmation timeout doesn't block traffic.
- Operator can roll back DNS independently if needed.

**Negative:**
- Writes during the gap fail. Apps must be written to retry on write
  failure — the contract is documented in `docs/architecture.md` §3.

**Neutral:**
- Both variants share the same Lambda set; only the state machine
  ordering differs.

## Alternatives Considered

- **Writer-first as default:** Rejected — penalizes the common case.
  Retained as a per-app flag.
- **Active-active writes:** Out of scope until Aurora Global writer-anywhere
  is acceptable (SPEC §14).
