# Step 02 — Clean, standardise and audit the source with a logged rule per decision

| | |
|---|---|
| **Command** | `pipeline/02_clean_standardize.py` |
| **Input** | data/interim/*.csv |
| **Output** | data/interim/clean_*.csv; reports/dq/02_data_quality_report.md, 02_dq_rules.json |

## What it does
snake_case columns, ISO dates, FK resolution (names/codes → ids), 24 rules (keys, FKs, driver-name conflict, cancelled-order anomalies, date reconciliation, purchase/hire date sanity, capacity unit, statistical shape).

## How to verify
See the matching row in docs/05_RUNBOOK.md and the generated report under `reports/`.

## Result (reference run)
0 key/FK failures; 27,979 driver-name mismatches; 252 cancelled orders mis-flagged; 6.6 % date inconsistencies within ±1 day; Dallas 122 % utilisation under the monthly-capacity reading.

## Notes
Every correction is a logged decision, never silent. See docs/04_DATA_QUALITY.md.
