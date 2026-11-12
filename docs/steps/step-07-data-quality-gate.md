# Step 07 — Executable quality gate over the warehouse

| | |
|---|---|
| **Command** | `pipeline/07_run_dq_checks.py` |
| **Input** | bronze/silver/gold |
| **Output** | reports/dq/07_pipeline_dq_results.{md,json}; exit code |

## What it does
13 SQL assertions returning violation counts; errors block, warnings inform.

## How to verify
See the matching row in docs/05_RUNBOOK.md and the generated report under `reports/`.

## Result (reference run)
13/13 PASS on the reference run.

## Notes
Use as a CI / scheduler gate.
