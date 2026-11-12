"""Leak-free feature engineering. PREDICTION POINT = the moment an order is dispatched.

Allowed: facts known at dispatch (route, parcel, driver, vehicle, hub processing time, calendar, weather, lagged hub history).
Forbidden (would leak the outcome): delivery_time_hours, delivered_at, delay_reason, csat_score, anything derived from them
for the same order. Hub history is lagged by 7 days because transit can take up to ~6 days to resolve.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CAT = ["hub_id", "service_level", "vehicle_type", "vehicle_model", "employment_type"]
NUM = ["distance_km", "package_weight_kg", "hub_processing_time_hours", "experience_years", "performance_rating", "driver_tenure_years",
       "vehicle_age_years", "breakdown_count_total", "maintenance_alert", "temp_c", "precip_mm", "wind_kmh", "is_severe_weather",
       "is_holiday", "is_weekend", "dow", "month", "created_hour_utc", "hub_delay_rate_lag7_28d", "hub_orders_prev7d"]
FEATURES = CAT + NUM


def _hub_history(df: pd.DataFrame) -> pd.DataFrame:
    days = pd.date_range(df.order_date.min(), df.order_date.max())
    out = []
    for hid, g in df.groupby("hub_id"):
        d = g.groupby("order_date").agg(created=("order_id", "size"), delivered=("is_cancelled", lambda s: int((~s).sum())),
                                        delayed=("is_delayed", "sum")).reindex(days, fill_value=0)
        roll = d[["delivered", "delayed"]].rolling(29, min_periods=7).sum().shift(7)
        out.append(pd.DataFrame({"hub_id": hid, "order_date": days,
                                 "hub_delay_rate_lag7_28d": roll.delayed / roll.delivered.replace(0, np.nan),
                                 "hub_orders_prev7d": d.created.rolling(7).sum().shift(1).values}))
    return pd.concat(out)


def build_features(orders: pd.DataFrame, drivers: pd.DataFrame, vehicles: pd.DataFrame) -> pd.DataFrame:
    df = orders.copy()
    df["order_date"] = pd.to_datetime(df["order_date"])
    df = df.merge(drivers[["driver_id", "employment_type", "experience_years", "performance_rating", "hire_date"]], on="driver_id", how="left")
    df = df.merge(vehicles[["vehicle_id", "vehicle_model", "vehicle_type", "purchase_date", "breakdown_count_total", "maintenance_alert"]],
                  on="vehicle_id", how="left")
    df["driver_tenure_years"] = (df.order_date - pd.to_datetime(df.hire_date)).dt.days / 365.25
    df["vehicle_age_years"] = (df.order_date - pd.to_datetime(df.purchase_date)).dt.days / 365.25
    df["created_hour_utc"] = pd.to_datetime(df.created_at, utc=True, format="ISO8601").dt.hour
    df["dow"], df["month"] = df.order_date.dt.dayofweek, df.order_date.dt.month
    for c in ["maintenance_alert", "is_severe_weather", "is_holiday", "is_weekend"]:
        df[c] = df[c].astype(float)
    df = df.merge(_hub_history(df), on=["hub_id", "order_date"], how="left")
    return df
