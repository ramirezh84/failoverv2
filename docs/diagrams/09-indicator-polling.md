# Diagram 09 — Indicator Polling (App side)

**Audience:** App engineers integrating with the orchestrator.

```mermaid
sequenceDiagram
  participant App as ECS task<br/>(every 15s)
  participant SSM as SSM Parameter Store<br/>(via VPC endpoint)
  participant Cache as In-process cache<br/>(last-known-good)
  participant Kafka as Kafka Consumer

  loop every 15s
    App->>SSM: GetParameter /failover/{app}/{region}/role
    alt success
      SSM-->>App: ACTIVE | PASSIVE | DRAINING
      App->>Cache: store
      App->>Kafka: pause if role != ACTIVE; resume if ACTIVE
    else error
      App->>Cache: read last-known-good (≤ 2 min old)
      alt cache stale (> 2 min)
        App->>Kafka: pause (fail-safe to PASSIVE)
      end
    end
  end
```
