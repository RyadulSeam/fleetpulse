# Step 05 — Land events in PostgreSQL bronze, safely

| | |
|---|---|
| **Command** | `pipeline/05_consume_to_postgres.py --source kafka|jsonl` |
| **Input** | Kafka topics (or JSONL) |
| **Output** | bronze.order_events, bronze.vehicle_telemetry, bronze.dead_letter, bronze.ingest_log |

## What it does
Validate → batch insert with ON CONFLICT DO NOTHING → log batch → commit offsets after DB commit. Invalid messages to dead-letter.

## How to verify
See the matching row in docs/05_RUNBOOK.md and the generated report under `reports/`.

## Result (reference run)
Backfill inserted 138,616 of 139,324 received (708 duplicates dropped); replaying the same file inserted 0 (tested).

## Notes
Effectively-once semantics from at-least-once delivery.
