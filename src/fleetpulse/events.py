"""Event model: converts enriched order rows into a stream of immutable, versioned business events.

Envelope (all topics):
  event_id        deterministic UUIDv5 -> re-sending the same business fact never creates a second row (idempotency)
  event_type      order_created | hub_received | dispatched | delivered | cancelled | feedback_received | vehicle_ping
  schema_version  integer, bumped on breaking payload changes
  event_time      when it happened in the (simulated) business world, ISO-8601 UTC
  produced_at     when the producer emitted it (wall clock) -> used to measure pipeline latency
  source          emitting system
  key / payload   entity id (order_id | vehicle_id) and the event body
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd

NS = uuid.UUID("6f1c3b0e-8f5a-4d7e-9a53-0a1b2c3d4e5f")
ORDER_EVENTS = {
    "order_created": ("created_at", ["hub_id", "destination_city", "dest_lat", "dest_lon", "distance_km", "service_level", "package_weight_kg"]),
    "hub_received": ("hub_received_at", ["hub_id"]),
    "dispatched": ("dispatched_at", ["hub_id", "driver_id", "vehicle_id", "hub_processing_time_hours"]),
    "delivered": ("delivered_at", ["hub_id", "driver_id", "vehicle_id", "delivery_time_hours", "is_delayed", "delay_reason"]),
    "cancelled": ("cancelled_at", ["hub_id", "driver_id", "vehicle_id", "cancellation_reason"]),
    "feedback_received": ("feedback_at", ["csat_score"]),
}


def event_id(*parts) -> str:
    return str(uuid.uuid5(NS, ":".join(str(p) for p in parts)))


def iso(ts) -> str:
    return pd.Timestamp(ts).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


INT_FIELDS = {"csat_score", "driver_id", "vehicle_id", "hub_id", "current_order_id"}


def _clean(v, key: str | None = None):
    if key in INT_FIELDS and v is not None and v is not pd.NA and not (isinstance(v, float) and np.isnan(v)):
        return int(v)          # schema says integer: never emit 4.0
    if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def build_order_events(orders: pd.DataFrame, version: int = 1, source: str = "fleetpulse-replay-simulator") -> pd.DataFrame:
    """Returns one row per event: [event_time(UTC ts), event_type, key, event_id, payload(dict)]."""
    parts = []
    for etype, (tcol, fields) in ORDER_EVENTS.items():
        sub = orders[orders[tcol].notna()]
        recs = sub[fields].astype(object).to_dict(orient="records")
        parts.append(pd.DataFrame({
            "event_time": sub[tcol].values,
            "event_type": etype,
            "key": sub["order_id"].astype(int).values,
            "payload": [{k: _clean(v, k) for k, v in r.items()} for r in recs],
        }))
    ev = pd.concat(parts, ignore_index=True)
    ev["event_time"] = pd.to_datetime(ev["event_time"], utc=True)
    ev["event_id"] = [event_id("order", k, t) for k, t in zip(ev.key, ev.event_type)]
    ev["schema_version"], ev["source"], ev["topic_kind"] = version, source, "orders"
    return ev.sort_values(["event_time", "key"]).reset_index(drop=True)


def build_telemetry(orders: pd.DataFrame, vehicles: pd.DataFrame, hubs: pd.DataFrame, start, end, ping_minutes: int,
                    max_radius_km: float, seed: int, version: int = 1, source: str = "fleetpulse-replay-simulator") -> pd.DataFrame:
    """SYNTHETIC vehicle heartbeat. Position follows the active order (hub -> destination) else idles near the home hub."""
    rng = np.random.default_rng(seed)
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    times = pd.date_range(start.ceil(f"{ping_minutes}min"), end, freq=f"{ping_minutes}min", inclusive="left")
    hub_xy = hubs.set_index("hub_id")[["lat", "lon"]]
    rows = []
    for v in vehicles[vehicles.home_hub_id.notna()].itertuples():
        vo = orders[(orders.vehicle_id == v.vehicle_id) & orders.dispatched_at.notna() & orders.delivered_at.notna()].sort_values("dispatched_at")
        hub_lat, hub_lon = hub_xy.loc[int(v.home_hub_id)]
        T = pd.DataFrame({"t": times})
        m = pd.merge_asof(T, vo[["dispatched_at", "delivered_at", "order_id", "dest_lat", "dest_lon"]], left_on="t", right_on="dispatched_at", direction="backward")
        active = m.delivered_at.notna() & (m.delivered_at > m.t)
        prog = ((m.t - m.dispatched_at) / (m.delivered_at - m.dispatched_at)).where(active, 0.0).astype(float)
        jitter = rng.normal(0, 0.004, (len(m), 2))
        lat = np.where(active, hub_lat + prog * (m.dest_lat - hub_lat), hub_lat) + jitter[:, 0]
        lon = np.where(active, hub_lon + prog * (m.dest_lon - hub_lon), hub_lon) + jitter[:, 1]
        n = len(m)
        fuel = np.clip(85 - (np.arange(n) % 220) * 0.35 + rng.normal(0, 1, n), 8, 100)
        rows.append(pd.DataFrame({
            "event_time": m.t, "key": int(v.vehicle_id), "event_type": "vehicle_ping",
            "payload": [{"vehicle_id": int(v.vehicle_id), "hub_id": int(v.home_hub_id), "lat": round(float(a), 5), "lon": round(float(b), 5),
                         "speed_kmh": round(float(s), 1), "fuel_pct": round(float(f), 1), "engine_temp_c": round(float(e), 1),
                         "status": "en_route" if act else "idle", "current_order_id": None if pd.isna(o) or not act else int(o)}
                        for a, b, s, f, e, act, o in zip(lat, lon, np.where(active, np.clip(rng.normal(42, 14, n), 0, 105), 0.0), fuel,
                                                         np.clip(rng.normal(90, 4, n), 70, 115), active, m.order_id)],
        }))
    if not rows:
        return pd.DataFrame(columns=["event_time", "event_type", "key", "event_id", "payload", "schema_version", "source", "topic_kind"])
    ev = pd.concat(rows, ignore_index=True)
    ev["event_id"] = [event_id("veh", k, t.isoformat()) for k, t in zip(ev.key, ev.event_time)]
    ev["schema_version"], ev["source"], ev["topic_kind"] = version, source, "telemetry"
    return ev.sort_values(["event_time", "key"]).reset_index(drop=True)


def to_envelope(row, produced_at: datetime | None = None) -> dict:
    produced_at = produced_at or datetime.now(timezone.utc)
    return {"event_id": row.event_id, "event_type": row.event_type, "schema_version": int(row.schema_version),
            "event_time": iso(row.event_time), "produced_at": produced_at.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "source": row.source, "key": int(row.key), "payload": row.payload}
