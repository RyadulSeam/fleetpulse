import json

import numpy as np
import pandas as pd
import pytest

from fleetpulse.events import build_order_events, event_id
from fleetpulse.geo import haversine_km
from fleetpulse.ingest import InvalidEvent, validate
from fleetpulse.ml import wilson


def test_haversine_dallas_houston():
    assert 360 < haversine_km(32.7767, -96.797, 29.7604, -95.3698) < 370


def test_event_id_is_deterministic_and_distinct():
    assert event_id("order", 1, "delivered") == event_id("order", 1, "delivered")
    assert event_id("order", 1, "delivered") != event_id("order", 1, "dispatched")


def _orders():
    t = pd.Timestamp("2024-05-01 10:00", tz="UTC")
    return pd.DataFrame({
        "order_id": [1, 2], "hub_id": [1, 2], "driver_id": [5, 6], "vehicle_id": [7, 8], "destination_city": ["A", "B"],
        "dest_lat": [1.0, 2.0], "dest_lon": [1.0, 2.0], "distance_km": [10.0, 20.0], "service_level": ["Standard"] * 2,
        "package_weight_kg": [1.0, 2.0], "hub_processing_time_hours": [2.0, 2.0], "delivery_time_hours": [10.0, np.nan],
        "is_delayed": [False, False], "delay_reason": [None, None], "cancellation_reason": [None, "Customer Not Home"],
        "csat_score": [4.0, np.nan],      # float because of NaN -> must be emitted as int
        "created_at": [t, t], "hub_received_at": [t, t], "dispatched_at": [t + pd.Timedelta(hours=2), pd.NaT],
        "delivered_at": [t + pd.Timedelta(hours=12), pd.NaT], "cancelled_at": [pd.NaT, t + pd.Timedelta(hours=1)],
        "feedback_at": [t + pd.Timedelta(hours=20), pd.NaT]})


def test_events_cover_lifecycle_and_types_are_integers():
    ev = build_order_events(_orders())
    assert set(ev[ev.key == 1].event_type) == {"order_created", "hub_received", "dispatched", "delivered", "feedback_received"}
    assert set(ev[ev.key == 2].event_type) == {"order_created", "hub_received", "cancelled"}
    fb = ev[ev.event_type == "feedback_received"].payload.iat[0]["csat_score"]
    assert isinstance(fb, int) and not isinstance(fb, bool)          # regression: 4.0 broke the SQL cast
    assert ev.event_time.is_monotonic_increasing
    json.dumps(list(ev.payload))                                       # JSON-safe (no NaN/numpy types)


def _env(**over):
    e = {"event_id": "x", "event_type": "delivered", "schema_version": 1, "event_time": "t", "produced_at": "t", "key": 1, "payload": {"csat_score": 4}}
    e.update(over)
    return e


def test_validation_rules():
    validate(_env(), "orders")
    for bad in (_env(schema_version=9), _env(event_type="nope"), _env(payload={"csat_score": 4.0}), _env(payload=[1])):
        with pytest.raises(InvalidEvent):
            validate(bad, "orders")
    with pytest.raises(InvalidEvent):
        validate(_env(event_type="vehicle_ping", payload={"lat": 999, "lon": 0}), "telemetry")


def test_wilson_interval_contains_rate():
    lo, hi = wilson(20, 100)
    assert lo < 0.2 < hi


def test_dst_ambiguous_hour_is_not_lost():
    """Regression: 2024-11-03 01:30 America/Chicago exists twice; the row must not become NaT."""
    s = pd.Series(pd.to_datetime(["2024-11-03 01:30"]))
    out = s.dt.tz_localize("America/Chicago", ambiguous=np.zeros(1, dtype=bool), nonexistent="shift_forward")
    assert out.notna().all()
