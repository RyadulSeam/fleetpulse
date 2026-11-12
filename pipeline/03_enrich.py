"""STEP 03 – Enrich: build the event timeline and add the context that real operations data has.

What is REAL vs DERIVED vs SYNTHETIC is recorded per column in reports/dq/03_column_provenance.json
and in docs/02_DATA_DICTIONARY.md. Nothing synthetic is hidden.

  SOURCE   : kept from the supplied files (durations, flags, CSAT, ids)
  EXTERNAL : real data from public free sources (Open-Meteo weather, US/TX holidays)
  DERIVED  : computed deterministically from source data (timestamps, utilisation helpers)
  SYNTHETIC: generated with a fixed seed (destination city, distance, package weight, service level,
             time-of-day, telemetry). Deliberately NOT correlated with delays (no fake signal injected).

Input : data/interim/clean_*.csv (Step 02)
Output: data/processed/{orders_enriched,dim_hub,dim_driver,dim_vehicle,dim_date,weather_daily}.csv
Flags : --require-real-weather  fail instead of using the flagged synthetic weather fallback
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import holidays
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fleetpulse.common import get_logger, load_config, path  # noqa: E402
from fleetpulse.geo import haversine_km  # noqa: E402
from fleetpulse.weather import load_weather  # noqa: E402

log = get_logger("step03")


def to_utc(local_naive: pd.Series, hub_ids: pd.Series, hubs_cfg: dict) -> pd.Series:
    out = pd.Series(pd.NaT, index=local_naive.index, dtype="datetime64[ns, UTC]")
    for hid, cfg in hubs_cfg.items():
        m = hub_ids == hid
        # DST fall-back hour exists twice; resolve to standard time (ambiguous=False) instead of dropping the row
        loc = local_naive[m].dt.tz_localize(cfg["tz"], ambiguous=np.zeros(int(m.sum()), dtype=bool), nonexistent="shift_forward")
        out[m] = loc.dt.tz_convert("UTC")
    return out


def main(require_real: bool) -> None:
    cfg = load_config()
    en, rng = cfg["enrichment"], np.random.default_rng(cfg["enrichment"]["seed"])
    hubs_cfg = {int(k): v for k, v in cfg["hubs"].items()}
    interim, out = path("interim"), path("processed")

    o = pd.read_csv(interim / "clean_orders.csv", parse_dates=["order_date", "source_delivery_date"])
    hubs = pd.read_csv(interim / "clean_hubs.csv")
    drivers = pd.read_csv(interim / "clean_drivers.csv", parse_dates=["hire_date"])
    vehicles = pd.read_csv(interim / "clean_vehicles.csv", parse_dates=["purchase_date"])
    n = len(o)

    # ---------- destinations & distance (SYNTHETIC, seeded) ----------
    city_lat, city_lon = np.empty(n), np.empty(n)
    names = np.empty(n, dtype=object)
    for hid, c in hubs_cfg.items():
        idx = np.where(o.hub_id.values == hid)[0]
        cities = list(c["cities"].items())
        pick = rng.integers(0, len(cities), len(idx))
        names[idx] = [cities[p][0] for p in pick]
        city_lat[idx] = [cities[p][1][0] for p in pick]
        city_lon[idx] = [cities[p][1][1] for p in pick]
    o["destination_city"], o["dest_lat"], o["dest_lon"] = names, city_lat, city_lon
    hub_lat, hub_lon = o.hub_id.map({k: v["lat"] for k, v in hubs_cfg.items()}), o.hub_id.map({k: v["lon"] for k, v in hubs_cfg.items()})
    o["distance_km"] = (haversine_km(hub_lat, hub_lon, o.dest_lat, o.dest_lon) * cfg["business_rules"]["road_distance_factor"]).round(1)

    # ---------- other synthetic descriptors ----------
    mix = en["service_level_mix"]
    o["service_level"] = rng.choice(list(mix), p=list(mix.values()), size=n)
    w = en["package_weight_kg"]
    o["package_weight_kg"] = np.clip(rng.lognormal(w["lognormal_mean"] - 2, w["lognormal_sigma"], n) * 2.7, w["min"], w["max"]).round(1)

    # ---------- timeline (DERIVED from source durations; time-of-day SYNTHETIC) ----------
    tod = en["created_time_of_day"]
    lag_h = rng.uniform(*[m / 60 for m in en["hub_receive_lag_minutes"]], n)
    t = np.clip(rng.normal(tod["mean_hour"], tod["sd_hours"], n), tod["min_hour"], tod["max_hour"])
    total = lag_h + o.hub_processing_time_hours.fillna(0).values + o.delivery_time_hours.fillna(0).values
    days = (o.source_delivery_date - o.order_date).dt.days.fillna(0).values
    delivered = ~o.is_cancelled.values
    # when a delivery date must be honoured, the full 24h clock is allowed (night-time orders exist in real operations)
    lo = np.maximum(0.0, 24 * days - total)
    hi = np.minimum(23.99, 24 * (days + 1) - total - 1e-6)
    feasible = delivered & (lo < hi)
    t = np.where(feasible, rng.uniform(np.where(feasible, lo, 0.0), np.where(feasible, hi, 1.0)), t)   # align to source delivery date when possible
    local_created = o.order_date + pd.to_timedelta(t, unit="h")
    o["created_at"] = to_utc(local_created, o.hub_id, hubs_cfg)
    assert o.created_at.notna().all(), "created_at must never be NaT (timezone conversion lost rows)"
    o["hub_received_at"] = o.created_at + pd.to_timedelta(lag_h, unit="h")
    o["dispatched_at"] = o.hub_received_at + pd.to_timedelta(o.hub_processing_time_hours, unit="h")
    o["delivered_at"] = (o.dispatched_at + pd.to_timedelta(o.delivery_time_hours, unit="h")).where(~o.is_cancelled)
    o["cancelled_at"] = o.dispatched_at.where(o.is_cancelled)
    o["dispatched_at"] = o.dispatched_at.where(~o.is_cancelled)
    fb = rng.uniform(*en["feedback_lag_hours"], n)
    o["feedback_at"] = (o.delivered_at + pd.to_timedelta(fb, unit="h")).where(o.csat_score.notna())
    # reconcile check against the source delivery date, in the hub's local time
    loc_deliv = pd.Series(pd.NaT, index=o.index, dtype="datetime64[ns]")
    for hid, c in hubs_cfg.items():
        m = (o.hub_id == hid) & o.delivered_at.notna()
        loc_deliv[m] = o.delivered_at[m].dt.tz_convert(c["tz"]).dt.tz_localize(None).dt.normalize()
    o["delivery_date_reconciled"] = (loc_deliv == o.source_delivery_date).where(delivered)
    rate = o.delivery_date_reconciled.dropna().astype(bool).mean()
    log.info("Delivered timestamps reconcile with the source delivery date for %.1f%% of orders", 100 * rate)

    # ---------- calendar (EXTERNAL: holidays lib) ----------
    tx = holidays.country_holidays("US", subdiv="TX", years=range(2022, 2026))
    o["is_weekend"] = o.order_date.dt.dayofweek >= 5
    o["is_holiday"] = o.order_date.dt.date.map(lambda d: d in tx)
    d = pd.date_range("2023-01-01", "2025-01-31")
    dim_date = pd.DataFrame({"date": d, "year": d.year, "quarter": d.quarter, "month": d.month, "month_name": d.strftime("%b"),
                             "iso_week": d.isocalendar().week.values, "day_of_week": d.dayofweek + 1, "day_name": d.strftime("%a"),
                             "is_weekend": d.dayofweek >= 5, "is_holiday": [x.date() in tx for x in d],
                             "holiday_name": [tx.get(x.date()) for x in d]})

    # ---------- weather (EXTERNAL; flagged fallback) ----------
    frames = []
    for hid, c in hubs_cfg.items():
        wdf = load_weather(hid, c["lat"], c["lon"], "2023-01-01", "2024-12-31", require_real)
        wdf.insert(0, "hub_id", hid)
        frames.append(wdf)
    weather = pd.concat(frames, ignore_index=True)
    weather["is_severe_weather"] = (weather.precip_mm >= 15) | (weather.wind_kmh >= 55) | weather.weather_code.isin([95, 96, 99])
    o = o.merge(weather.rename(columns={"date": "order_date"}), on=["hub_id", "order_date"], how="left")
    log.info("Weather source mix: %s", o.weather_source.value_counts().to_dict())

    # ---------- dimensions ----------
    dim_hub = hubs.assign(lat=hubs.hub_id.map({k: v["lat"] for k, v in hubs_cfg.items()}),
                          lon=hubs.hub_id.map({k: v["lon"] for k, v in hubs_cfg.items()}),
                          timezone=hubs.hub_id.map({k: v["tz"] for k, v in hubs_cfg.items()}))

    # ---------- write ----------
    cols = ["order_id", "order_date", "order_status", "is_cancelled", "is_delayed", "delay_reason", "cancellation_reason", "hub_id",
            "driver_id", "vehicle_id", "service_level", "package_weight_kg", "destination_city", "dest_lat", "dest_lon", "distance_km",
            "created_at", "hub_received_at", "dispatched_at", "delivered_at", "cancelled_at", "feedback_at",
            "hub_processing_time_hours", "delivery_time_hours", "csat_score", "source_delivery_date", "delivery_date_reconciled",
            "is_weekend", "is_holiday", "temp_c", "precip_mm", "wind_kmh", "weather_code", "is_severe_weather", "weather_source",
            "vehicle_before_purchase", "driver_before_hire"]
    o[cols].sort_values("order_id").to_csv(out / "orders_enriched.csv", index=False)
    dim_hub.to_csv(out / "dim_hub.csv", index=False)
    drivers.to_csv(out / "dim_driver.csv", index=False)
    vehicles.to_csv(out / "dim_vehicle.csv", index=False)
    dim_date.to_csv(out / "dim_date.csv", index=False)
    weather.to_csv(out / "weather_daily.csv", index=False)

    prov = {"SOURCE": ["order_id", "order_date", "order_status", "is_delayed*", "delay_reason", "hub_id", "driver_id", "vehicle_id",
                       "hub_processing_time_hours", "delivery_time_hours", "csat_score", "source_delivery_date"],
            "EXTERNAL": ["temp_c", "precip_mm", "wind_kmh", "weather_code", "is_severe_weather", "is_holiday", "lat/lon of hubs & cities"],
            "DERIVED": ["created_at*", "hub_received_at", "dispatched_at", "delivered_at", "cancelled_at", "feedback_at",
                        "distance_km (from synthetic city)", "is_weekend", "delivery_date_reconciled"],
            "SYNTHETIC": ["destination_city", "dest_lat", "dest_lon", "service_level", "package_weight_kg", "time-of-day of created_at",
                          "vehicle telemetry (Step 04)"],
            "NOTE": "* is_delayed corrected in Step 02 (cancelled != delayed). Weather rows carry weather_source = open-meteo | synthetic_fallback."}
    (path("reports_dq") / "03_column_provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")
    log.info("Enriched orders: %s rows x %s cols -> data/processed/", len(o), len(cols))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--require-real-weather", action="store_true")
    main(ap.parse_args().require_real_weather)
