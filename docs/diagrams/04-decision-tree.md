# Diagram 04 — Decision Tree

**Audience:** Engineers debugging false positives / negatives.

```mermaid
flowchart TD
  Start[Decision Engine tick] --> Quorum{count(Tier1 red)<br/>>= tier1_quorum?}
  Quorum -- no --> StateGreen[state=GREEN<br/>or WATCHING]
  Quorum -- yes --> Dwell{red continuous<br/>>= dwell_minutes?}
  Dwell -- no --> StateWatching[state=WATCHING<br/>reason=dwell_not_held]
  Dwell -- yes --> Hyst{time_since_last<br/>>= hysteresis?}
  Hyst -- no --> StateWatching2[state=WATCHING<br/>reason=hysteresis_blocked]
  Hyst -- yes --> Auto{auto_failover==true?}
  Auto -- no --> AlertOnly[FAILOVER_AUTHORIZED_BUT_NOT_AUTO<br/>SNS HIGH only]
  Auto -- yes --> Safe{secondary_safe?}
  Safe -- no --> Unsafe[FAILOVER_AUTHORIZED_BUT_UNSAFE<br/>SNS CRITICAL]
  Safe -- yes --> Authorized[FAILOVER_AUTHORIZED<br/>emit control metric=0.0<br/>SNS CRITICAL]
```
