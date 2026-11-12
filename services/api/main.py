"""FleetPulse API – serves the delay/ETA models and warehouse KPIs.  Run:  uvicorn services.api.main:app --reload --port 8000

Every prediction response carries `model_status`, derived from reports/ml/metrics.json, so a consumer can never mistake a
model with no proven signal for a reliable one.
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fleetpulse.features import FEATURES  # noqa: E402
from fleetpulse.common import path  # noqa: E402

app = FastAPI(title="FleetPulse API", version="1.0.0", description="Logistics intelligence: predictions, forecasts and KPIs.")


class OrderFeatures(BaseModel):
    hub_id: int = Field(..., ge=1, le=6)
    service_level: str = "Standard"
    vehicle_type: str = "Van"
    vehicle_model: str = "Mercedes Sprinter"
    employment_type: str = "Full-time"
    distance_km: float = 30.0
    package_weight_kg: float = 10.0
    hub_processing_time_hours: float = 2.0
    experience_years: float = 4
    performance_rating: float = 4
    driver_tenure_years: float = 3.0
    vehicle_age_years: float = 3.0
    breakdown_count_total: float = 10
    maintenance_alert: float = 0
    temp_c: float = 20.0
    precip_mm: float = 0.0
    wind_kmh: float = 15.0
    is_severe_weather: float = 0
    is_holiday: float = 0
    is_weekend: float = 0
    dow: int = Field(2, ge=0, le=6)
    month: int = Field(6, ge=1, le=12)
    created_hour_utc: int = Field(14, ge=0, le=23)
    hub_delay_rate_lag7_28d: float = 0.20
    hub_orders_prev7d: float = 45


@lru_cache(maxsize=1)
def _models():
    d = path("models")
    if not (d / "delay_model.joblib").exists():
        raise HTTPException(503, "Models not trained yet. Run: python pipeline/08_train_models.py")
    return joblib.load(d / "delay_model.joblib"), joblib.load(d / "eta_model.joblib")


@lru_cache(maxsize=1)
def _status() -> dict:
    fp = path("reports_ml") / "metrics.json"
    if not fp.exists():
        return {"reliable_signal": False, "note": "metrics.json missing"}
    m = json.loads(fp.read_text())
    return {"delay_reliable_signal": m["delay_classifier"]["verdict"]["reliable_signal"], "delay_auc_ci95": m["delay_classifier"][m["delay_classifier"]["verdict"]["best_model"]]["auc_ci95"],
            "eta_reliable_signal": m["eta_regressor"]["reliable_signal"], "eta_skill_vs_baseline": m["eta_regressor"]["skill_vs_hub_median"]}


@app.get("/health")
def health():
    return {"status": "ok", "models_available": (path("models") / "delay_model.joblib").exists()}


@app.get("/model-status")
def model_status():
    return _status()


@app.post("/predict")
def predict(x: OrderFeatures):
    delay_m, eta_m = _models()
    row = pd.DataFrame([x.model_dump()])[FEATURES]
    s = _status()
    return {"delay_probability": round(float(delay_m.predict(row)[0]), 4), "eta_transit_hours": round(float(np.asarray(eta_m.predict(row))[0]), 2),
            "model_status": {"delay": "reliable" if s.get("delay_reliable_signal") else "NOT RELIABLE – no proven signal, do not use for decisions",
                             "eta": "reliable" if s.get("eta_reliable_signal") else "not better than per-hub median baseline"}, "evidence": s}


@app.get("/forecast/{hub_id}")
def forecast(hub_id: int):
    fp = path("forecast_output") / "forecast_daily_hub.csv"
    if not fp.exists():
        raise HTTPException(503, "Forecast not generated. Run: python pipeline/09_forecast_demand.py")
    df = pd.read_csv(fp)
    df = df[df.hub_id == hub_id]
    if df.empty:
        raise HTTPException(404, f"unknown hub {hub_id}")
    return {"hub_id": hub_id, "model": df.model_name.iat[0], "generated_from": df.generated_from.iat[0],
            "forecast": df[["forecast_date", "yhat", "yhat_lo", "yhat_hi"]].to_dict(orient="records")}
