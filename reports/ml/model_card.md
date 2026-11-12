# Model card – FleetPulse delay & ETA models

*Generated automatically by `pipeline/08_train_models.py`. Numbers below are from the untouched test period (Oct–Dec 2024, 3,497 delivered orders).*

## 1. Delay classifier (will a dispatched order be late?)
| Model | ROC-AUC (95% CI) | PR-AUC (base rate 0.209) | Brier | Top-decile lift |
|---|---|---|---|---|
| Baseline (prevalence) | 0.500 | – | 0.1652 | 1.00 |
| Logistic regression | 0.502 (0.478–0.526) | 0.214 | 0.1654 | 1.00 |
| LightGBM | 0.490 (0.468–0.513) | 0.203 | 0.1653 | 0.85 |

**Pre-registered verdict rule:** useful only if the AUC *lower* bound > 0.55. Best model = `logistic_regression`, lower bound = 0.478.
### Verdict: ❌ NO reliable predictive signal at dispatch time. The model is NOT recommended for operational decisions.

Why this is an honest and useful result: delays in this dataset are statistically almost indistinguishable across hubs, vehicles, drivers, weather and calendar (see `segments.csv`, chi-square tests, and Step 02 rule R13). What *does* separate delayed from on-time orders (long transit time, low CSAT) is only observable AFTER the fact, so using it would be target leakage. The platform therefore reports rules-based segmentation and monitoring KPIs rather than a misleading score.

## 2. ETA regressor (transit hours)
MAE: LightGBM **18.63h** vs hub-median baseline **18.68h** vs global-mean 18.85h · R² -0.008 · skill vs baseline **0.3%** → not materially better than a simple per-hub median.

## 3. Segmentation (rules-based)
Overall delay rate 20.4%. Dimensions tested: 10; significant after Bonferroni correction (alpha 0.05/10): **0**.

## 4. Data, features and leakage controls
- Prediction point: dispatch. Excluded: delivery hours, delivered timestamps, delay reason, CSAT.
- Features (25): route/parcel (synthetic distance, weight, service level), driver & vehicle attributes, hub processing hours, calendar, weather, lagged hub delay history (lag 7 days).
- Time-ordered split; no shuffling; test set used once.
- **Limitations:** distance, weight, service level and destination are synthetic (Step 03) and independent of delays by construction; weather may be synthetic fallback unless Open-Meteo was reachable (`weather_source`). Vehicle breakdown/maintenance columns are *current snapshots* applied to history.
- Top LightGBM features (share of gain): {"vehicle_age_years": 0.1654, "hub_delay_rate_lag7_28d": 0.1184, "precip_mm": 0.0809, "package_weight_kg": 0.0746, "hub_processing_time_hours": 0.069, "created_hour_utc": 0.0638, "hub_orders_prev7d": 0.0613, "driver_tenure_years": 0.0612}

## 5. Intended use
Monitoring and analysis. Not for automated decisions about drivers.
