# Step 01 — Normalise encoding and profile the raw files

| | |
|---|---|
| **Command** | `pipeline/01_convert_and_profile.py` |
| **Input** | data/raw/*.csv (UTF-16) |
| **Output** | data/interim/*.csv (UTF-8); reports/dq/01_raw_profile.{md,json} |

## What it does
Detect encoding from the BOM; read with the right codec; write UTF-8; compute rows, dtypes, nulls, distinct counts, duplicate rows per file.

## How to verify
See the matching row in docs/05_RUNBOOK.md and the generated report under `reports/`.

## Result (reference run)
Row counts 27,979 / 55 / 6 / 45; encoding reported as utf-16 for all four.

## Notes
Nothing is cleaned here by design: this step only makes the data readable and measurable.
