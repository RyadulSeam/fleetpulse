# Data quality

Two layers, both automated and both producing reports under `reports/dq/`:

## 1. Source audit (Step 02) — 24 rules → `reports/dq/02_data_quality_report.md`
Highest-impact findings (reference run) and the decision taken for each:

| ID | Finding | Rows | Decision |
|---|---|---:|---|
| R03 | `Orders.Driver Name` ≠ master name for the same Driver ID | 27,979 (100 %) | master is authoritative; copy dropped |
| R07a | Cancelled orders flagged "delayed" | 252 (100 % of cancelled) | delay only applies to delivered orders |
| R07b | Cancelled orders have CSAT = 1 placeholder | 252 | set to NULL |
| R05 | Same vehicle model under several vehicle types | 6 of 9 models | type moved to dim, conflict documented |
| R08a | Delivery date ≠ order date + ⌊(processing+delivery h)/24⌋ | 1,830 (6.6 %) — always within ±1 day | hours authoritative |
| R09a/b | Vehicle used before purchase / driver before hire | 782 / 1,193 | kept, flagged |
| R12 | Hub capacity unit undocumented | 6 hubs | assumed orders/month (ADR-0003) |
| R13 | Delay reasons uniformly distributed (χ² p = 0.67); delay vs hub p = 0.20 | – | expect weak ML signal |

## 2. Warehouse gate (Step 07) — 13 checks → `reports/dq/07_pipeline_dq_results.md`
Blocking (error): completeness of `order_created`, ≤ 6 events per order, timeline monotonicity, dimension resolution, delayed-flag/reason consistency,
cancelled-order rules, CSAT range, telemetry ranges. Non-blocking (warn): dead letters, stuck orders, ingestion latency, row-count reconciliation.
Exit code 1 on any blocking failure ⇒ usable as a CI/orchestrator gate.

## Bugs the checks and tests caught during development (kept as regression tests)
1. 11 orders silently lost: DST "fall-back" hour (2023-11-05, 2024-11-03) became `NaT` → fixed + assertion + test.
2. `csat_score` emitted as `4.0` (float) broke the SQL integer cast → producer cast + consumer validation + test.
3. Live replay window contained almost no new orders (cut-off based on last delivery instead of last creation) → fixed.
4. Cancelled events lacked driver/vehicle → 252 orders failed dimension resolution → payload extended.
