# ML & forecasting methodology

Auto-generated results live in `reports/ml/model_card.md`, `metrics.json`, `segments.csv`, `forecast_backtest.json`.

## Principles
1. **Pre-registered verdict:** a model is *useful* only if the bootstrap 95 % lower bound of ROC-AUC exceeds 0.55 (`configs/settings.yaml`). The rule is fixed before seeing results.
2. **No leakage:** prediction point = dispatch. Forbidden: delivery hours, delivered timestamps, delay reason, CSAT (they define or follow the outcome). Hub history is lagged 7 days.
3. **Time-ordered split:** train ≤ 2024-06-30, validation ≤ 2024-09-30, test = Oct–Dec 2024, touched once.
4. **Baselines first:** prevalence / global mean / per-hub median / seasonal-naive. A model must beat them.
5. **Report failure:** if there is no signal, say so and fall back to rules-based segmentation.

## Models
| Model | Target | Algorithms | Result (reference run) |
|---|---|---|---|
| Delay classifier | late delivery | prevalence, logistic regression, LightGBM | AUC ≈ 0.50 (CI 0.48–0.52) → **no reliable signal**; API labels it NOT RELIABLE |
| ETA regressor | transit hours | global mean, per-hub median, LightGBM (L1) | MAE 18.65 h vs 18.68 h baseline → skill 0.2 % (none) |
| Segmentation | delay rate by 10 dimensions | Wilson CIs + χ² with Bonferroni | 0 significant dimensions |
| Demand forecast | orders per hub per day, 14 d ahead | seasonal-naive, 28-day MA, LightGBM direct | LightGBM WAPE 0.314 vs 0.336 / 0.382 (6-fold rolling-origin backtest) |
| Fleet risk | breakdown propensity | transparent scoring rule (SQL) | 8 High / 22 Medium / 15 Low |

## Why the delay model fails (and why that is the right answer)
The strongest correlates of delay in the data — long transit time and low CSAT — are *consequences* of the delay and unknown at dispatch.
Everything knowable at dispatch (hub, driver, vehicle, route, weather, calendar) is statistically unrelated to delay in this dataset.
Synthetic features cannot help: they are independent of delays by construction. **Do not "fix" this by injecting correlated synthetic data.**

## What would make delay prediction work in real life
GPS dwell/stop data, traffic, carrier scan events (intermediate hub arrivals), exact promised delivery windows, route plans, real parcel attributes.
