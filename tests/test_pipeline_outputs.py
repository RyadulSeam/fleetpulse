"""Contract tests on pipeline artifacts (run after steps 01-03)."""
from pathlib import Path

import pandas as pd
import pytest

P = Path(__file__).resolve().parents[1] / "data" / "processed" / "orders_enriched.csv"
pytestmark = pytest.mark.skipif(not P.exists(), reason="run steps 01-03 first")


@pytest.fixture(scope="module")
def o():
    d = pd.read_csv(P)
    for c in ["created_at", "hub_received_at", "dispatched_at", "delivered_at", "cancelled_at", "feedback_at"]:
        d[c] = pd.to_datetime(d[c], utc=True, format="ISO8601")
    return d


def test_row_count_and_unique_ids(o):
    assert len(o) == 27979 and o.order_id.is_unique


def test_no_missing_creation_timestamp(o):
    assert o.created_at.notna().all()


def test_timeline_is_ordered(o):
    d = o[~o.is_cancelled]
    assert (d.hub_received_at >= d.created_at).all() and (d.dispatched_at >= d.hub_received_at).all() and (d.delivered_at >= d.dispatched_at).all()


def test_cancelled_orders_are_not_delayed_and_have_no_csat(o):
    c = o[o.is_cancelled]
    assert (~c.is_delayed).all() and c.csat_score.isna().all() and c.delivered_at.isna().all()


def test_delay_reason_iff_delayed(o):
    d = o[~o.is_cancelled]
    assert (d.is_delayed == d.delay_reason.notna()).all()


def test_source_durations_preserved(o):
    d = o[~o.is_cancelled]
    got = (d.delivered_at - d.dispatched_at).dt.total_seconds() / 3600
    assert (got - d.delivery_time_hours).abs().max() < 1e-3


def test_date_reconciliation_rate_documented_threshold(o):
    assert o.delivery_date_reconciled.dropna().astype(bool).mean() > 0.90


def test_weather_source_is_always_labelled(o):
    assert set(o.weather_source.unique()) <= {"open-meteo", "synthetic_fallback"}
