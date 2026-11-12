"""STEP 09 – Demand forecasting (orders created per hub per day, 14 days ahead).

Method
  * Candidates: seasonal-naive (mean of last 4 same-weekdays), 28-day moving average, LightGBM "direct 14-day" model
    (features use only data >= 14 days older than the target day, so there is no recursion and no leakage).
  * Rolling-origin backtest over the last 91 days (origins every 14 days). Best model is chosen by WAPE on the backtest,
    NOT by hope: if LightGBM does not beat the baselines it is not used.
  * Prediction intervals = empirical 10th/90th percentile of backtest residuals of the chosen model (per hub).
Output: configured forecast_output/ and reports_ml/ directories, gold.forecast_daily_hub (+ gold.ml_metrics)
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import holidays
import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fleetpulse.common import get_logger, load_config, path, pg_connect  # noqa: E402
from fleetpulse.ml import write_metrics_db  # noqa: E402

warnings.filterwarnings("ignore")
log = get_logger("step09")
H = 14   # forecast horizon == minimum lag


def make_panel(orders: pd.DataFrame, end: pd.Timestamp) -> pd.DataFrame:
    d = orders.groupby(["hub_id", "order_date"]).size().rename("y").reset_index()
    idx = pd.MultiIndex.from_product([sorted(d.hub_id.unique()), pd.date_range(d.order_date.min(), end)], names=["hub_id", "order_date"])
    return d.set_index(["hub_id", "order_date"]).reindex(idx).reset_index()   # future days -> NaN


def add_features(p: pd.DataFrame, tx) -> pd.DataFrame:
    p = p.sort_values(["hub_id", "order_date"]).copy()
    g = p.groupby("hub_id").y
    for k in (14, 21, 28, 35):
        p[f"lag_{k}"] = g.shift(k)
    p["roll28_lag14"] = g.transform(lambda s: s.shift(H).rolling(28, min_periods=14).mean())
    p["roll7_lag14"] = g.transform(lambda s: s.shift(H).rolling(7, min_periods=4).mean())
    od = p.order_date
    p["dow"], p["month"], p["doy_sin"], p["doy_cos"] = od.dt.dayofweek, od.dt.month, np.sin(2 * np.pi * od.dt.dayofyear / 365.25), np.cos(2 * np.pi * od.dt.dayofyear / 365.25)
    p["is_holiday"] = od.dt.date.map(lambda x: x in tx).astype(int)
    return p


FEATS = ["hub_id", "lag_14", "lag_21", "lag_28", "lag_35", "roll28_lag14", "roll7_lag14", "dow", "month", "doy_sin", "doy_cos", "is_holiday"]


def seasonal_naive(known: pd.Series, target: pd.Timestamp, origin: pd.Timestamp) -> float:
    vals = [known.get(target - pd.Timedelta(days=7 * k)) for k in range(1, 9) if target - pd.Timedelta(days=7 * k) <= origin]
    vals = [v for v in vals if v is not None and not np.isnan(v)][:4]
    return float(np.mean(vals)) if vals else np.nan


def fit_gbm(train: pd.DataFrame, seed: int):
    m = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.04, num_leaves=15, min_child_samples=30, subsample=0.8, subsample_freq=1,
                          colsample_bytree=0.8, reg_lambda=3, random_state=seed, verbose=-1)
    return m.fit(train[FEATS], train.y)


def main(use_db: bool) -> None:
    cfg = load_config()["ml"]
    orders = pd.read_csv(path("processed") / "orders_enriched.csv", parse_dates=["order_date"])
    data_end = orders.order_date.max()
    tx = holidays.country_holidays("US", subdiv="TX", years=range(2022, 2026))
    panel = add_features(make_panel(orders, data_end + pd.Timedelta(days=H)), tx)
    known = panel[panel.order_date <= data_end]
    log.info("panel: %s hubs, %s days (%s -> %s)", panel.hub_id.nunique(), known.order_date.nunique(), known.order_date.min().date(), data_end.date())

    # ---------- rolling-origin backtest ----------
    origins = [data_end - pd.Timedelta(days=H * i) for i in range(cfg["forecast"]["backtest_days"] // H, 0, -1)]
    rows = []
    for o in origins:
        train = known[(known.order_date <= o) & known.lag_14.notna() & known.lag_35.notna()]
        gbm = fit_gbm(train, cfg["seed"])
        test = known[(known.order_date > o) & (known.order_date <= o + pd.Timedelta(days=H))].copy()
        test["lightgbm"] = gbm.predict(test[FEATS])
        for hid, g in test.groupby("hub_id"):
            hist = known[(known.hub_id == hid) & (known.order_date <= o)].set_index("order_date").y
            ma = hist.tail(28).mean()
            for r in g.itertuples():
                rows.append({"origin": o, "hub_id": hid, "date": r.order_date, "y": r.y, "lightgbm": r.lightgbm,
                             "seasonal_naive": seasonal_naive(hist, r.order_date, o), "moving_avg_28": ma})
    bt = pd.DataFrame(rows).dropna()
    models = ["seasonal_naive", "moving_avg_28", "lightgbm"]
    score = {m: {"wape": float((bt[m] - bt.y).abs().sum() / bt.y.sum()), "bias_pct": float((bt[m] - bt.y).sum() / bt.y.sum() * 100),
                 "mae": float((bt[m] - bt.y).abs().mean())} for m in models}
    best = min(models, key=lambda m: score[m]["wape"])
    for m in models:
        log.info("backtest %-15s WAPE %.3f | bias %+.1f%% | MAE %.2f", m, score[m]["wape"], score[m]["bias_pct"], score[m]["mae"])
    log.info("selected model: %s", best)

    # ---------- final forecast ----------
    train = known[known.lag_14.notna() & known.lag_35.notna()]
    fut = panel[panel.order_date > data_end].copy()
    if best == "lightgbm":
        fut["yhat"] = fit_gbm(train, cfg["seed"]).predict(fut[FEATS])
    else:
        fut["yhat"] = [seasonal_naive(known[known.hub_id == r.hub_id].set_index("order_date").y, r.order_date, data_end) if best == "seasonal_naive"
                       else known[known.hub_id == r.hub_id].y.tail(28).mean() for r in fut.itertuples()]
    resid = (bt.y - bt[best]).groupby(bt.hub_id).quantile([0.1, 0.9]).unstack()
    fut["yhat_lo"] = (fut.yhat + fut.hub_id.map(resid[0.1])).clip(lower=0)
    fut["yhat_hi"] = fut.yhat + fut.hub_id.map(resid[0.9])
    fut = fut.rename(columns={"order_date": "forecast_date"})[["hub_id", "forecast_date", "yhat", "yhat_lo", "yhat_hi"]].round(2)
    fut["model_name"], fut["generated_from"] = best, data_end.date().isoformat()
    fut.to_csv(path("forecast_output") / "forecast_daily_hub.csv", index=False)

    per_hub = {int(h): float((g[best] - g.y).abs().sum() / g.y.sum()) for h, g in bt.groupby("hub_id")}
    out = {"backtest_folds": len(origins), "backtest_rows": len(bt), "scores": score, "selected": best, "wape_by_hub": per_hub,
           "interpretation": "WAPE = sum|error| / sum(actual). Lower is better. Compare against the baselines, not against zero."}
    (path("reports_ml") / "forecast_backtest.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    bt.assign(model=best).to_csv(path("reports_ml") / "forecast_backtest_rows.csv", index=False)

    if use_db:
        rows_m = [(f"forecast_{m}", "wape", s["wape"], "backtest") for m, s in score.items()] + [("forecast", "selected_" + best, 1.0, "backtest winner")]
        ok = write_metrics_db(rows_m)
        try:
            conn = pg_connect()
            with conn, conn.cursor() as cur:
                cur.execute("""CREATE TABLE IF NOT EXISTS gold.forecast_daily_hub (hub_id int, forecast_date date, yhat double precision,
                               yhat_lo double precision, yhat_hi double precision, model_name text, generated_from date,
                               PRIMARY KEY (hub_id, forecast_date))""")
                cur.execute("TRUNCATE gold.forecast_daily_hub")
                for r in fut.itertuples(index=False):
                    cur.execute("INSERT INTO gold.forecast_daily_hub VALUES (%s,%s,%s,%s,%s,%s,%s)", tuple(r))
            conn.close()
            log.info("forecast loaded into gold.forecast_daily_hub (metrics saved: %s)", ok)
        except Exception as exc:
            log.warning("database not available, CSV only (%s)", type(exc).__name__)
    log.info("Forecast (%s days x %s hubs) -> %s", H, fut.hub_id.nunique(), path("forecast_output") / "forecast_daily_hub.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-db", action="store_true")
    main(not ap.parse_args().no_db)
