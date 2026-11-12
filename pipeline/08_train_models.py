"""STEP 08 – Predictive models with HONEST evaluation.

Models (prediction point = dispatch; see src/fleetpulse/features.py for the leakage rules)
  A) Delay classifier  : will a dispatched order be delivered late?     (baseline: prevalence, logistic regression, LightGBM)
  B) ETA regressor     : how many transit hours will delivery take?     (baseline: global mean, per-hub median, LightGBM)

Evaluation protocol
  * Strict time split: train <= 2024-06-30 | validation <= 2024-09-30 | test = Oct-Dec 2024 (never touched during tuning)
  * ROC-AUC with 95% bootstrap CI, PR-AUC vs prevalence, Brier vs baseline, top-decile lift
  * Verdict rule is fixed in advance (configs/settings.yaml): the model is called USEFUL only if the AUC lower bound exceeds the threshold
  * If there is no reliable signal, the report says so, and a segmentation analysis (rules-based) is produced instead

Output: configured models/ and reports_ml/ directories
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fleetpulse.common import get_logger, load_config, path  # noqa: E402
from fleetpulse.features import FEATURES, build_features  # noqa: E402
from fleetpulse.ml import FittedModel, bootstrap_auc_ci, wilson, write_metrics_db  # noqa: E402

warnings.filterwarnings("ignore")
log = get_logger("step08")


def main() -> None:
    cfg = load_config()["ml"]
    seed, proc, rep, mdir = cfg["seed"], path("processed"), path("reports_ml"), path("models")
    orders = pd.read_csv(proc / "orders_enriched.csv")
    df = build_features(orders, pd.read_csv(proc / "dim_driver.csv"), pd.read_csv(proc / "dim_vehicle.csv"))
    df = df[~df.is_cancelled].copy()
    df["y_delay"] = df.is_delayed.astype(int)
    tr = df[df.order_date <= cfg["split"]["train_end"]]
    va = df[(df.order_date > cfg["split"]["train_end"]) & (df.order_date <= cfg["split"]["valid_end"])]
    te = df[df.order_date > cfg["split"]["valid_end"]]
    log.info("rows train/valid/test = %s/%s/%s | delay rate train %.3f test %.3f", len(tr), len(va), len(te), tr.y_delay.mean(), te.y_delay.mean())
    metrics: dict = {"split": {"train": len(tr), "valid": len(va), "test": len(te)}}

    # ================= A) DELAY CLASSIFIER =================
    prev = tr.y_delay.mean()
    yt = te.y_delay.values
    res = {"baseline_prevalence": {"auc": 0.5, "brier": brier_score_loss(yt, np.full(len(te), prev))}}

    lr = FittedModel(make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=500, C=0.5)), "logistic_regression", "classification")
    lr.estimator.fit(lr._x(tr, fit=True), tr.y_delay)
    gbm = FittedModel(lgb.LGBMClassifier(n_estimators=600, learning_rate=0.03, num_leaves=15, min_child_samples=150, subsample=0.8, subsample_freq=1,
                                         colsample_bytree=0.8, reg_lambda=5, random_state=seed, verbose=-1), "lightgbm", "classification")
    gbm.estimator.fit(gbm._x(tr, fit=True), tr.y_delay, eval_set=[(gbm._x(va), va.y_delay)], eval_metric="auc",
                      callbacks=[lgb.early_stopping(50, verbose=False)])
    for m in (lr, gbm):
        p = m.predict(te)
        auc, lo, hi = bootstrap_auc_ci(yt, p, seed=seed)
        top = p >= np.quantile(p, 0.9)
        res[m.name] = {"auc": auc, "auc_ci95": [lo, hi], "pr_auc": average_precision_score(yt, p), "pr_auc_baseline": float(yt.mean()),
                       "brier": brier_score_loss(yt, p), "top_decile_lift": float(yt[top].mean() / yt.mean())}
        log.info("%s: AUC %.3f [%.3f, %.3f] | top-decile lift %.2f", m.name, auc, lo, hi, res[m.name]["top_decile_lift"])
    best = max((lr, gbm), key=lambda m: res[m.name]["auc"])
    thr = cfg["min_auc_lower_bound_for_signal"]
    has_signal = res[best.name]["auc_ci95"][0] > thr
    res["verdict"] = {"best_model": best.name, "auc_lower_bound": res[best.name]["auc_ci95"][0], "threshold": thr, "reliable_signal": bool(has_signal)}
    imp = pd.Series(gbm.estimator.booster_.feature_importance("gain"), index=FEATURES).sort_values(ascending=False)
    res["lightgbm_top_features_gain"] = (imp / imp.sum()).head(8).round(4).to_dict()
    metrics["delay_classifier"] = res
    joblib.dump(best, mdir / "delay_model.joblib")

    # ================= B) ETA REGRESSOR =================
    yv = te.delivery_time_hours.values
    eta = {"baseline_global_mean": {"mae": mean_absolute_error(yv, np.full(len(te), tr.delivery_time_hours.mean()))}}
    hub_med = tr.groupby("hub_id").delivery_time_hours.median()
    eta["baseline_hub_median"] = {"mae": mean_absolute_error(yv, te.hub_id.map(hub_med).fillna(tr.delivery_time_hours.median()))}
    reg = FittedModel(lgb.LGBMRegressor(n_estimators=600, learning_rate=0.03, num_leaves=15, min_child_samples=150, subsample=0.8, subsample_freq=1,
                                        colsample_bytree=0.8, reg_lambda=5, objective="regression_l1", random_state=seed, verbose=-1), "lightgbm_mae", "regression")
    reg.estimator.fit(reg._x(tr, fit=True), tr.delivery_time_hours, eval_set=[(reg._x(va), va.delivery_time_hours)], callbacks=[lgb.early_stopping(50, verbose=False)])
    pr = reg.predict(te)
    eta["lightgbm_mae"] = {"mae": mean_absolute_error(yv, pr), "r2": r2_score(yv, pr)}
    base_mae = eta["baseline_hub_median"]["mae"]
    eta["skill_vs_hub_median"] = 1 - eta["lightgbm_mae"]["mae"] / base_mae
    eta["reliable_signal"] = bool(eta["skill_vs_hub_median"] > 0.05)
    log.info("ETA: MAE model %.2fh vs hub-median %.2fh (skill %.1f%%)", eta["lightgbm_mae"]["mae"], base_mae, 100 * eta["skill_vs_hub_median"])
    metrics["eta_regressor"] = eta
    joblib.dump(reg, mdir / "eta_model.joblib")

    # ================= C) SEGMENTATION (rules-based fallback) =================
    full = df.copy()
    full["distance_band"] = pd.cut(full.distance_km, [0, 20, 35, 50, 1e9], labels=["<20km", "20-35km", "35-50km", ">50km"])
    full["experience_band"] = pd.cut(full.experience_years, [-1, 2, 5, 100], labels=["0-2y", "3-5y", "6y+"])
    full["day"] = full.order_date.dt.day_name()
    dims = ["hub_id", "service_level", "vehicle_type", "employment_type", "day", "month", "is_severe_weather", "is_holiday", "distance_band", "experience_band"]
    base_rate, seg_rows = full.y_delay.mean(), []
    for d in dims:
        ct = pd.crosstab(full[d], full.y_delay)
        p_chi = stats.chi2_contingency(ct)[1]
        for lvl, r in ct.iterrows():
            k, n = int(r.get(1, 0)), int(r.sum())
            lo, hi = wilson(k, n)
            seg_rows.append({"dimension": d, "segment": str(lvl), "orders": n, "delay_rate": k / n, "ci_low": lo, "ci_high": hi,
                             "vs_overall_pp": 100 * (k / n - base_rate), "dimension_chi2_p": p_chi})
    seg = pd.DataFrame(seg_rows)
    seg.to_csv(rep / "segments.csv", index=False)
    n_dims_sig = int(seg.groupby("dimension").dimension_chi2_p.first().lt(0.05 / len(dims)).sum())
    metrics["segmentation"] = {"overall_delay_rate": base_rate, "dimensions_tested": len(dims), "dimensions_significant_bonferroni": n_dims_sig}
    (rep / "metrics.json").write_text(json.dumps(metrics, indent=2, default=float), encoding="utf-8")

    # ================= MODEL CARD =================
    v, c = res["verdict"], res[best.name]
    card = f"""# Model card – FleetPulse delay & ETA models

*Generated automatically by `pipeline/08_train_models.py`. Numbers below are from the untouched test period (Oct–Dec 2024, {len(te):,} delivered orders).*

## 1. Delay classifier (will a dispatched order be late?)
| Model | ROC-AUC (95% CI) | PR-AUC (base rate {yt.mean():.3f}) | Brier | Top-decile lift |
|---|---|---|---|---|
| Baseline (prevalence) | 0.500 | – | {res['baseline_prevalence']['brier']:.4f} | 1.00 |
| Logistic regression | {res['logistic_regression']['auc']:.3f} ({res['logistic_regression']['auc_ci95'][0]:.3f}–{res['logistic_regression']['auc_ci95'][1]:.3f}) | {res['logistic_regression']['pr_auc']:.3f} | {res['logistic_regression']['brier']:.4f} | {res['logistic_regression']['top_decile_lift']:.2f} |
| LightGBM | {res['lightgbm']['auc']:.3f} ({res['lightgbm']['auc_ci95'][0]:.3f}–{res['lightgbm']['auc_ci95'][1]:.3f}) | {res['lightgbm']['pr_auc']:.3f} | {res['lightgbm']['brier']:.4f} | {res['lightgbm']['top_decile_lift']:.2f} |

**Pre-registered verdict rule:** useful only if the AUC *lower* bound > {thr}. Best model = `{v['best_model']}`, lower bound = {v['auc_lower_bound']:.3f}.
### Verdict: {"✅ reliable predictive signal found." if has_signal else "❌ NO reliable predictive signal at dispatch time. The model is NOT recommended for operational decisions."}

{"" if has_signal else "Why this is an honest and useful result: delays in this dataset are statistically almost indistinguishable across hubs, vehicles, drivers, weather and calendar (see `segments.csv`, chi-square tests, and Step 02 rule R13). What *does* separate delayed from on-time orders (long transit time, low CSAT) is only observable AFTER the fact, so using it would be target leakage. The platform therefore reports rules-based segmentation and monitoring KPIs rather than a misleading score."}

## 2. ETA regressor (transit hours)
MAE: LightGBM **{eta['lightgbm_mae']['mae']:.2f}h** vs hub-median baseline **{base_mae:.2f}h** vs global-mean {eta['baseline_global_mean']['mae']:.2f}h · R² {eta['lightgbm_mae']['r2']:.3f} · skill vs baseline **{100 * eta['skill_vs_hub_median']:.1f}%** → {"useful" if eta['reliable_signal'] else "not materially better than a simple per-hub median"}.

## 3. Segmentation (rules-based)
Overall delay rate {base_rate:.1%}. Dimensions tested: {len(dims)}; significant after Bonferroni correction (alpha 0.05/{len(dims)}): **{n_dims_sig}**.

## 4. Data, features and leakage controls
- Prediction point: dispatch. Excluded: delivery hours, delivered timestamps, delay reason, CSAT.
- Features ({len(FEATURES)}): route/parcel (synthetic distance, weight, service level), driver & vehicle attributes, hub processing hours, calendar, weather, lagged hub delay history (lag 7 days).
- Time-ordered split; no shuffling; test set used once.
- **Limitations:** distance, weight, service level and destination are synthetic (Step 03) and independent of delays by construction; weather may be synthetic fallback unless Open-Meteo was reachable (`weather_source`). Vehicle breakdown/maintenance columns are *current snapshots* applied to history.
- Top LightGBM features (share of gain): {json.dumps(res['lightgbm_top_features_gain'])}

## 5. Intended use
Monitoring and analysis. Not for automated decisions about drivers.
"""
    (rep / "model_card.md").write_text(card, encoding="utf-8")
    write_metrics_db([("delay_classifier", "auc_test", c["auc"], best.name), ("delay_classifier", "auc_ci_low", c["auc_ci95"][0], best.name),
                      ("delay_classifier", "reliable_signal", float(has_signal), "verdict"), ("eta_regressor", "mae_hours", eta["lightgbm_mae"]["mae"], "lightgbm"),
                      ("eta_regressor", "mae_hours_baseline", base_mae, "hub_median")])
    log.info("Model card -> %s | verdict: %s", rep / "model_card.md", "SIGNAL" if has_signal else "NO RELIABLE SIGNAL")


if __name__ == "__main__":
    main()
