# Step 06 — Create dimensions, silver and gold layers

| | |
|---|---|
| **Command** | `pipeline/06_build_warehouse.py` |
| **Input** | sql/*.sql; data/processed/dim_*.csv |
| **Output** | schemas bronze/silver/gold with views |

## What it does
DDL, TRUNCATE+COPY dimensions, CREATE OR REPLACE VIEW for silver/gold. Fully idempotent.

## How to verify
See the matching row in docs/05_RUNBOOK.md and the generated report under `reports/`.

## Result (reference run)
Warehouse totals equal source exactly: 27,727 delivered, 5,656 delayed, 22,071 on-time, CSAT 4.197, mean delivery 35.78 h, per-hub on-time rates identical.

## Notes
Safe to re-run at any time, including during live ingestion.
