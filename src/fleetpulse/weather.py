"""Daily weather for each hub: real (Open-Meteo archive API, free, no key) with a clearly-flagged fallback."""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import requests

from .common import get_logger, load_config, path

log = get_logger("weather")
RENAME = {"temperature_2m_mean": "temp_c", "precipitation_sum": "precip_mm", "wind_speed_10m_max": "wind_kmh", "weather_code": "weather_code"}


_API_DOWN = False   # fail fast: once the host is unreachable, don't retry for every hub


def fetch_open_meteo(lat: float, lon: float, start: str, end: str, retries: int = 3) -> pd.DataFrame:
    global _API_DOWN
    if _API_DOWN:
        raise RuntimeError("Open-Meteo unreachable (skipped after first failure)")
    cfg = load_config()["enrichment"]["weather"]
    params = {"latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
              "daily": ",".join(cfg["daily_vars"]), "timezone": "auto"}
    last = None
    for i in range(retries):
        try:
            r = requests.get(cfg["url"], params=params, timeout=60)
            r.raise_for_status()
            d = r.json()["daily"]
            df = pd.DataFrame(d).rename(columns={"time": "date", **RENAME})
            df["date"] = pd.to_datetime(df["date"])
            df["weather_source"] = "open-meteo"
            return df
        except requests.exceptions.ConnectionError as exc:   # DNS / no internet: retrying will not help
            _API_DOWN = True
            raise RuntimeError(f"Open-Meteo unreachable ({type(exc).__name__})") from exc
        except Exception as exc:  # HTTP 5xx / timeout / bad JSON: worth retrying
            last = exc
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"Open-Meteo unavailable: {last}")


def synthetic_fallback(lat: float, start: str, end: str, seed: int) -> pd.DataFrame:
    """Plausible Texas climatology. NOT real weather – flagged as such in every row."""
    rng = np.random.default_rng(seed)
    d = pd.date_range(start, end, freq="D")
    doy = d.dayofyear.values
    temp = 19 + 11 * np.sin(2 * np.pi * (doy - 110) / 365) + rng.normal(0, 3, len(d)) - (lat - 30) * 0.4
    rain = rng.random(len(d)) < 0.18
    precip = np.where(rain, rng.exponential(7, len(d)), 0.0).round(1)
    wind = (rng.lognormal(2.7, 0.35, len(d))).round(1)
    code = np.where(precip > 15, 95, np.where(precip > 2, 63, np.where(precip > 0, 51, 1)))
    return pd.DataFrame({"date": d, "temp_c": temp.round(1), "precip_mm": precip, "wind_kmh": wind,
                         "weather_code": code, "weather_source": "synthetic_fallback"})


def load_weather(hub_id: int, lat: float, lon: float, start: str, end: str, require_real: bool = False) -> pd.DataFrame:
    cache = path("external") / f"weather_hub{hub_id}.csv"
    if cache.exists():
        df = pd.read_csv(cache, parse_dates=["date"])
        if (df.weather_source == "open-meteo").all() and df.date.min() <= pd.Timestamp(start) and df.date.max() >= pd.Timestamp(end):
            log.info("hub %s: using cached real weather", hub_id)
            return df
    try:
        df = fetch_open_meteo(lat, lon, start, end)
        log.info("hub %s: fetched %s days from Open-Meteo", hub_id, len(df))
    except RuntimeError as exc:
        if require_real or not load_config()["enrichment"]["weather"]["allow_synthetic_fallback"]:
            raise
        log.warning("hub %s: %s -> using FLAGGED synthetic fallback", hub_id, exc)
        df = synthetic_fallback(lat, start, end, seed=load_config()["enrichment"]["seed"] + hub_id)
    df.to_csv(cache, index=False)
    return df
