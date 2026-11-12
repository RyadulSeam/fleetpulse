"""FleetPulse – live operations dashboard (Streamlit).  Run:  streamlit run services/dashboard/app.py

Reads ONLY the gold layer. The "clock" is the simulated world clock (newest event), because the source is a replay.
Auto-refreshes every few seconds so events from the running replay/consumer appear live.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fleetpulse.common import sa_engine, path  # noqa: E402

st.set_page_config(page_title="FleetPulse – Live Operations", page_icon="🚚", layout="wide")


@st.cache_resource
def engine():
    return sa_engine()


def q(sql: str) -> pd.DataFrame:
    try:
        return pd.read_sql(text(sql), engine())   # text(): '%' in LIKE is not a bind marker
    except Exception as exc:  # table/view missing or DB down: show a friendly message, don't crash the page
        st.warning(f"Data not available yet ({type(exc).__name__}). Run the pipeline steps 05–06 first.")
        return pd.DataFrame()


st.title("🚚 FleetPulse – Live Operations")
st.caption("Simulated real-time: historical logistics data replayed as an event stream (Kafka → PostgreSQL → this dashboard).")

with st.sidebar:
    refresh = st.select_slider("Auto-refresh (seconds)", [3, 5, 10, 30], value=5)
    st.markdown("**Data provenance**\n- Orders/durations/CSAT: supplied dataset\n- Weather: Open-Meteo (or flagged fallback)\n- Telemetry, destinations, weights: synthetic")


@st.fragment(run_every=refresh)
def live():
    clock = q("SELECT sim_now FROM gold.sim_clock")
    if clock.empty or clock.sim_now.iat[0] is None:
        st.info("Waiting for events… start the consumer (Step 05) and the replay (Step 04).")
        return
    now = pd.Timestamp(clock.sim_now.iat[0])
    st.subheader(f"Simulated time: {now:%Y-%m-%d %H:%M} UTC")

    k = q(f"""SELECT count(*) FILTER (WHERE order_status IN ('created','at_hub','in_transit')) AS in_flight,
              count(*) FILTER (WHERE created_at >= TIMESTAMPTZ '{now}' - interval '24 hours') AS created_24h,
              count(*) FILTER (WHERE delivered_at >= TIMESTAMPTZ '{now}' - interval '24 hours') AS delivered_24h,
              round(100.0 * count(*) FILTER (WHERE is_on_time AND delivered_at >= TIMESTAMPTZ '{now}' - interval '7 days')
                    / NULLIF(count(*) FILTER (WHERE order_status='delivered' AND delivered_at >= TIMESTAMPTZ '{now}' - interval '7 days'),0),1) AS on_time_7d,
              round(avg(csat_score) FILTER (WHERE feedback_at >= TIMESTAMPTZ '{now}' - interval '7 days'),2) AS csat_7d
              FROM gold.fct_orders""")
    c = st.columns(5)
    for col, (label, key, fmt) in zip(c, [("In flight", "in_flight", "{:,.0f}"), ("Created (24h)", "created_24h", "{:,.0f}"), ("Delivered (24h)", "delivered_24h", "{:,.0f}"),
                                          ("On-time % (7d)", "on_time_7d", "{:.1f}"), ("CSAT (7d)", "csat_7d", "{:.2f}")]):
        v = k[key].iat[0] if not k.empty else None
        col.metric(label, "–" if v is None or pd.isna(v) else fmt.format(float(v)))

    left, right = st.columns([3, 2])
    with left:
        st.markdown("##### Fleet positions (latest ping per vehicle)")
        pos = q("SELECT p.vehicle_id, v.vehicle_code, p.lat, p.lon, p.status, p.speed_kmh, p.fuel_pct FROM silver.vehicle_latest_position p JOIN gold.dim_vehicle v USING (vehicle_id)")
        if not pos.empty:
            pos["color"] = pos.status.map({"en_route": [0, 160, 90, 200], "idle": [150, 150, 150, 180]})
            st.pydeck_chart(pdk.Deck(map_style=None, initial_view_state=pdk.ViewState(latitude=31.2, longitude=-98.5, zoom=4.6),
                                     layers=[pdk.Layer("ScatterplotLayer", pos, get_position="[lon, lat]", get_fill_color="color", get_radius=9000, pickable=True)],
                                     tooltip={"text": "{vehicle_code}\n{status} · {speed_kmh} km/h\nfuel {fuel_pct}%"}))
            st.caption("Telemetry is synthetic (see docs/02_DATA_DICTIONARY.md).")
    with right:
        st.markdown("##### Orders in flight")
        fl = q("SELECT order_id, hub_name, order_status, service_level, destination_city, age_hours FROM gold.live_orders_in_flight ORDER BY age_hours DESC LIMIT 12")
        if not fl.empty:
            st.dataframe(fl, hide_index=True, width="stretch")
        else:
            st.info("No active orders in the current replay snapshot.")

    a, b = st.columns(2)
    with a:
        st.markdown("##### Hub utilisation (this month, vs capacity)")
        u = q("SELECT hub_name, orders_created, capacity, utilization FROM gold.kpi_hub_utilization_monthly WHERE month = (SELECT max(month) FROM gold.kpi_hub_utilization_monthly) ORDER BY hub_name")
        if not u.empty:
            u["utilization_%"] = (u.utilization.astype(float) * 100).round(0)
            st.bar_chart(u.set_index("hub_name")["utilization_%"])
            over = u[u["utilization_%"] > 100]
            if len(over):
                st.error("Over capacity: " + ", ".join(over.hub_name))
    with b:
        st.markdown("##### Weekly delay rate by hub")
        cc = q("""
            SELECT hub_id, hub_name, week_start, delivered, delayed,
                   delay_rate, centre_line, lcl, ucl, out_of_control
            FROM gold.delay_control_chart_weekly
            WHERE week_start IS NOT NULL
            ORDER BY week_start, hub_name
        """)

        if not cc.empty:
            chart = cc.copy()
            chart["week_start"] = pd.to_datetime(chart["week_start"])
            pivot = chart.pivot(
                index="week_start",
                columns="hub_name",
                values="delay_rate"
            )
            st.line_chart(pivot)
            st.dataframe(chart, hide_index=True, width="stretch")

            if cc["out_of_control"].fillna(False).any():
                st.warning("One or more weeks exceeded the upper control limit.")
            else:
                st.caption("No weeks breached the 3-sigma upper control limit in the current data.")

            st.caption("The current replay covers a short period. More weeks are needed before drawing conclusions about long-term process stability.")
        else:
            st.info("No weekly delivery data is available yet.")


@st.fragment(run_every=refresh)
def health():
    s = q("SELECT * FROM gold.ingest_summary")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Ingestion summary")
        st.dataframe(s, hide_index=True, width="stretch")
        st.caption("duplicates_dropped > 0 is expected: the replay deliberately re-sends some events; idempotent writes discard them.")
    with c2:
        st.markdown("##### Latency (producer → bronze), recent minutes")
        ph = q("SELECT minute, events_ingested, avg_latency_seconds FROM gold.pipeline_health ORDER BY minute ASC LIMIT 30")
        if not ph.empty:
            st.line_chart(ph.set_index("minute")["avg_latency_seconds"])


tab1, tab2, tab3, tab4 = st.tabs(["Live operations", "Demand forecast", "ML transparency", "Pipeline health"])
with tab1:
    live()
with tab2:
    fc = q("SELECT hub_id, forecast_date, yhat, yhat_lo, yhat_hi, model_name FROM gold.forecast_daily_hub ORDER BY hub_id, forecast_date")
    if not fc.empty:
        hubs = q("SELECT hub_id, hub_name FROM gold.dim_hub ORDER BY hub_id")
        name = st.selectbox("Hub", hubs.hub_name)
        hid = int(hubs[hubs.hub_name == name].hub_id.iat[0])
        f = fc[fc.hub_id == hid].set_index("forecast_date")[["yhat_lo", "yhat", "yhat_hi"]]
        st.line_chart(f)
        st.caption(f"Model: {fc.model_name.iat[0]} (14-day direct forecast, 80% interval from backtest residuals).")
        bt = q("SELECT model, value AS wape FROM gold.ml_metrics WHERE model LIKE 'forecast_%' AND metric='wape' AND run_at = (SELECT max(run_at) FROM gold.ml_metrics WHERE model LIKE 'forecast_%')")
        if not bt.empty:
            st.markdown("**Backtest WAPE (lower is better)**")
            st.dataframe(bt.round(3), hide_index=True)
with tab3:
    mc = path("reports_ml") / "model_card.md"
    st.markdown(mc.read_text(encoding="utf-8") if mc.exists() else "Run Step 08 to generate the model card.")
with tab4:
    health()
