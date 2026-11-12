# Step 03 — Build the event timeline and add real external context

| | |
|---|---|
| **Command** | `pipeline/03_enrich.py [--require-real-weather]` |
| **Input** | data/interim/clean_*.csv; Open-Meteo API; holidays library |
| **Output** | data/processed/{orders_enriched,dim_*,weather_daily}.csv; reports/dq/03_column_provenance.json |

## What it does
UTC timestamps from order date + source durations (time-of-day synthetic, constrained to honour the source delivery date), DST-safe; synthetic destination/distance/weight/service level (seeded, independent of delays); real weather per hub-day; US/TX holidays; dimensions with lat/lon/timezone.

## How to verify
See the matching row in docs/05_RUNBOOK.md and the generated report under `reports/`.

## Result (reference run)
92.3 % of delivered timestamps reconcile with the source delivery date; 0 missing creation timestamps (assertion); weather rows carry weather_source.

## Notes
Fails fast if created_at is ever NaT. With no internet the weather falls back to flagged synthetic data.
