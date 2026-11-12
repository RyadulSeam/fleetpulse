# Step 07 – Warehouse data-quality gate

| ID | Status | Severity | Check | Violations | Detail |
|---|---|---|---|---:|---|
| C01 | PASS | error | Every order has an order_created event | 0 |  |
| C02 | PASS | error | No order has more than 6 events (one per event type) | 0 |  |
| C03 | PASS | error | Timeline order: created <= hub_received <= dispatched <= delivered | 0 |  |
| C04 | FAIL | error | Orders resolve to hub, driver and vehicle dimensions | 1 |  |
| C05 | PASS | error | Delivered orders carry an is_delayed flag | 0 |  |
| C06 | PASS | error | delay_reason present if and only if delayed | 0 |  |
| C07 | PASS | error | Cancelled orders are never 'delayed' and have no CSAT | 0 |  |
| C08 | PASS | error | CSAT within 1-5 | 0 |  |
| C09 | PASS | error | Telemetry coordinates/fuel/speed within valid ranges | 0 |  |
| C10 | PASS | warn | No dead-letter messages | 0 |  |
| C11 | PASS | warn | Stuck orders (not finished 10+ sim-days after creation) | 0 |  |
| C12 | WARN | warn | Ingestion latency under 60s (producer -> bronze) for live events | 560 |  |
| C13 | WARN | warn | Warehouse order count equals source order count (see detail) | 136 | warehouse=27,843 source=27,979 |