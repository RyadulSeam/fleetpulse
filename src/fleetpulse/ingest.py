"""Validation + bronze-table writers (shared by the consumer and by tests)."""
from __future__ import annotations

import json
from pathlib import Path

from psycopg2.extras import execute_values

SUPPORTED_VERSIONS = {1}
ORDER_TYPES = {"order_created", "hub_received", "dispatched", "delivered", "cancelled", "feedback_received"}
REQUIRED = {"event_id", "event_type", "schema_version", "event_time", "produced_at", "key", "payload"}
TELEMETRY_FIELDS = ["vehicle_id", "hub_id", "lat", "lon", "speed_kmh", "fuel_pct", "engine_temp_c", "status", "current_order_id"]


class InvalidEvent(ValueError):
    pass


def validate(ev: dict, kind: str) -> dict:
    missing = REQUIRED - ev.keys()
    if missing:
        raise InvalidEvent(f"missing fields {sorted(missing)}")
    if ev["schema_version"] not in SUPPORTED_VERSIONS:
        raise InvalidEvent(f"unsupported schema_version {ev['schema_version']}")
    if not isinstance(ev["payload"], dict):
        raise InvalidEvent("payload must be an object")
    if kind == "orders" and ev["event_type"] not in ORDER_TYPES:
        raise InvalidEvent(f"unknown order event_type {ev['event_type']}")
    for f in ("csat_score", "driver_id", "vehicle_id", "hub_id"):
        v = ev["payload"].get(f)
        if v is not None and (isinstance(v, bool) or not isinstance(v, int)):
            raise InvalidEvent(f"{f} must be an integer, got {v!r}")
    if kind == "telemetry":
        if ev["event_type"] != "vehicle_ping":
            raise InvalidEvent(f"unknown telemetry event_type {ev['event_type']}")
        lat, lon = ev["payload"].get("lat"), ev["payload"].get("lon")
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise InvalidEvent("invalid coordinates")
    return ev


def write_orders(cur, rows: list[tuple]) -> int:
    """rows: (event_id,type,version,event_time,produced_at,order_id,payload_json,topic,partition,offset). Returns inserted count."""
    out = execute_values(cur, """INSERT INTO bronze.order_events
        (event_id,event_type,schema_version,event_time,produced_at,order_id,payload,kafka_topic,kafka_partition,kafka_offset)
        VALUES %s ON CONFLICT (event_id) DO NOTHING RETURNING event_id""", rows, fetch=True)
    return len(out)


def write_telemetry(cur, rows: list[tuple]) -> int:
    out = execute_values(cur, """INSERT INTO bronze.vehicle_telemetry
        (event_id,event_time,produced_at,vehicle_id,hub_id,lat,lon,speed_kmh,fuel_pct,engine_temp_c,status,current_order_id)
        VALUES %s ON CONFLICT (event_id) DO NOTHING RETURNING event_id""", rows, fetch=True)
    return len(out)


def to_order_row(ev: dict, topic=None, part=None, off=None) -> tuple:
    return (ev["event_id"], ev["event_type"], ev["schema_version"], ev["event_time"], ev["produced_at"], ev["key"],
            json.dumps(ev["payload"]), topic, part, off)


def to_telemetry_row(ev: dict) -> tuple:
    p = ev["payload"]
    return (ev["event_id"], ev["event_time"], ev["produced_at"], *[p.get(f) for f in TELEMETRY_FIELDS])


def apply_sql(conn, files: list[Path]) -> None:
    with conn.cursor() as cur:
        for f in files:
            cur.execute(f.read_text(encoding="utf-8"))
    conn.commit()
