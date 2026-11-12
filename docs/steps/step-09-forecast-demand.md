# Step 09 — 14-day demand forecast per hub with backtest-based model selection

| | |
|---|---|
| **Command** | `pipeline/09_forecast_demand.py` |
| **Input** | data/processed/orders_enriched.csv |
| **Output** | data/processed/forecast_daily_hub.csv; gold.forecast_daily_hub; reports/ml/forecast_backtest.json |

## What it does
Direct 14-day LightGBM vs seasonal-naive vs 28-day MA; 6-fold rolling-origin backtest; model chosen by WAPE; 80 % interval from backtest residuals.

## How to verify
See the matching row in docs/05_RUNBOOK.md and the generated report under `reports/`.

## Result (reference run)
WAPE: LightGBM 0.314, seasonal-naive 0.336, MA-28 0.382; selected LightGBM; 84 forecast rows (6 hubs × 14 days from 2025-01-01).

## Notes
Gain over baseline is modest: daily hub volumes are only 6-10 orders.
