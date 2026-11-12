# Step 08 — Train and honestly evaluate delay and ETA models; segmentation fallback

| | |
|---|---|
| **Command** | `pipeline/08_train_models.py` |
| **Input** | data/processed/orders_enriched.csv, dims |
| **Output** | models/*.joblib; reports/ml/{metrics.json,model_card.md,segments.csv}; gold.ml_metrics |

## What it does
Leak-free features at dispatch time, time-ordered split, baselines, bootstrap AUC CI, pre-registered verdict, auto-generated model card, 10-dimension segmentation with Bonferroni.

## How to verify
See the matching row in docs/05_RUNBOOK.md and the generated report under `reports/`.

## Result (reference run)
Delay AUC ≈ 0.50 [0.48, 0.52] → NO RELIABLE SIGNAL; ETA skill 0.2 %; 0 of 10 dimensions significant.

## Notes
A negative result is a deliverable: it prevents a bad model from reaching operations.
