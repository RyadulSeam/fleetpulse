# Step 04 — Publish history as a real-time event stream

| | |
|---|---|
| **Command** | `pipeline/04_replay_stream.py --mode backfill|live --sink kafka|jsonl --speed N` |
| **Input** | data/processed/*.csv |
| **Output** | Kafka topics fleetpulse.order_events / fleetpulse.vehicle_telemetry, or data/stream/*.jsonl |

## What it does
Six order event types per order with deterministic IDs; synthetic vehicle heartbeats in the live window; injected duplicates (0.5 %) and late events (1 %); pacing by simulated-seconds-per-second; backfill (history, unpaced) vs live (last 3 days of creation + delivery tail, paced).

## How to verify
See the matching row in docs/05_RUNBOOK.md and the generated report under `reports/`.

## Result (reference run)
139,391 unique order events across backfill + live (27,979 orders), plus ≈ 14.4 k unique telemetry pings in the live window.

## Notes
Run with --sink jsonl --speed 0 for an instant dry run without Docker.
