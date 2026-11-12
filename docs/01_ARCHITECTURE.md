# Architecture

## Layers (medallion)
| Layer | Where | Contents | Rule |
|---|---|---|---|
| Landing | Kafka topics | `fleetpulse.order_events`, `fleetpulse.vehicle_telemetry` (3 partitions, key = order_id / vehicle_id) | immutable, at-least-once |
| **Bronze** | `bronze.*` tables | raw events (`payload jsonb`), dead-letter, ingest log | append-only, idempotent on `event_id` |
| **Silver** | `silver.*` views | one row per order (pivot of its events), latest vehicle position | no ordering assumptions: aggregate over *all* events, so late/duplicate events self-heal |
| **Gold** | `gold.*` | dims, `fct_orders`, KPI marts, driver scorecard, fleet risk, forecast, ML metrics, pipeline health | business definitions live here only |

## Components
| Component | Technology | Why |
|---|---|---|
| Broker | Redpanda (Kafka API) | single binary, free, Kafka-compatible clients; swap for Kafka/MSK/Confluent unchanged |
| Warehouse | PostgreSQL 16 | free, ubiquitous, Power BI connects natively; fits the data volume (≈140 k events) |
| Transform | plain SQL views (+ Python for enrichment) | transparent and testable; dbt migration is an optional upgrade (ADR-0002) |
| ML | scikit-learn, LightGBM | industry standard tabular stack |
| Serving | FastAPI | typed contracts, auto-docs at `/docs` |
| Live UI | Streamlit (`st.fragment` auto-refresh) | fast to build, pydeck map |
| CI | GitHub Actions | free for public repos |

## Key design decisions
- **Idempotency:** `event_id = UUIDv5(order_id, event_type)`; consumer uses `ON CONFLICT DO NOTHING`; offsets committed after DB commit ⇒ effectively-once.
- **Simulated clock:** dashboards read `gold.sim_clock` (newest event time), never wall-clock, because the source is a replay.
- **Failure isolation:** invalid messages → `bronze.dead_letter`; the stream never blocks.
- **Backfill + live:** history is bulk-loaded; the last N days are replayed paced. Same code path, different `--mode`.

## Data flow of one order
`order_created → hub_received → dispatched → delivered → feedback_received` (or `… → cancelled`).
Telemetry is a separate high-volume topic (vehicle ping every 30 simulated minutes).

## Scalability notes (honest)
Current volume (~140 k events) is small. The same design scales by adding partitions/consumers; PostgreSQL would move to a
columnar warehouse (BigQuery/Snowflake/ClickHouse) beyond ~100 M rows. Not implemented here; not needed here.
