# Diagram 04 — Decision Tree

**Audience:** Engineers debugging false positives / negatives.

```mermaid
flowchart TD
  Start[Decision Engine tick] --> Quorum{quorum held}
  Quorum -- no --> StateGreen[GREEN or WATCHING]
  Quorum -- yes --> Dwell{dwell held}
  Dwell -- no --> StateWatchingD[WATCHING dwell_not_held]
  Dwell -- yes --> Hyst{hysteresis held}
  Hyst -- no --> StateWatchingH[WATCHING hysteresis_blocked]
  Hyst -- yes --> Auto{auto_failover true}
  Auto -- no --> AlertOnly[FAILOVER_AUTHORIZED_BUT_NOT_AUTO SNS HIGH]
  Auto -- yes --> Safe{secondary_safe}
  Safe -- no --> Unsafe[FAILOVER_AUTHORIZED_BUT_UNSAFE SNS CRITICAL]
  Safe -- yes --> Authorized[FAILOVER_AUTHORIZED control_metric 0.0 SNS CRITICAL]
```

The choice nodes are intentionally short (mermaid flowchart parser dislikes
parens and HTML entities inside `{...}` choice labels). For the full
expansion of each gate — quorum threshold, dwell window, hysteresis window,
secondary readiness check — see [`docs/decision-engine.md`](../decision-engine.md) §3.
