-- GOLD: business-ready views. Metric definitions live in docs/07_KPI_DEFINITIONS.md (single source of truth).

-- "Now" of the simulated world = newest event seen. Dashboards use this clock, never wall-clock time.
CREATE OR REPLACE VIEW gold.sim_clock AS
SELECT max(event_time) AS sim_now FROM bronze.order_events;

CREATE OR REPLACE VIEW gold.fct_orders AS
SELECT
    o.*,
    h.hub_name, h.timezone,
    (o.created_at AT TIME ZONE h.timezone)::date                                    AS order_date,
    d.driver_name, d.employment_type, d.experience_years, d.performance_rating,
    v.vehicle_code, v.vehicle_model, v.vehicle_type,
    (o.order_status = 'delivered' AND NOT o.is_delayed)                             AS is_on_time,
    EXTRACT(EPOCH FROM (o.delivered_at - o.created_at)) / 3600.0                    AS cycle_time_hours,
    w.temp_c, w.precip_mm, w.wind_kmh, w.is_severe_weather, w.weather_source
FROM silver.orders o
LEFT JOIN gold.dim_hub     h ON h.hub_id = o.hub_id
LEFT JOIN gold.dim_driver  d ON d.driver_id = o.driver_id
LEFT JOIN gold.dim_vehicle v ON v.vehicle_id = o.vehicle_id
LEFT JOIN gold.weather_daily w ON w.hub_id = o.hub_id AND w.date = (o.created_at AT TIME ZONE h.timezone)::date;

CREATE OR REPLACE VIEW gold.kpi_daily_hub AS
SELECT
    order_date, hub_id, hub_name,
    count(*)                                                        AS orders_created,
    count(*) FILTER (WHERE order_status = 'delivered')              AS orders_delivered,
    count(*) FILTER (WHERE order_status = 'cancelled')              AS orders_cancelled,
    count(*) FILTER (WHERE is_delayed)                              AS orders_delayed,
    count(*) FILTER (WHERE is_on_time)                              AS orders_on_time,
    round((count(*) FILTER (WHERE is_on_time))::numeric / NULLIF(count(*) FILTER (WHERE order_status = 'delivered'), 0), 4) AS on_time_rate,
    round((count(*) FILTER (WHERE order_status = 'cancelled'))::numeric / NULLIF(count(*), 0), 4)                          AS cancellation_rate,
    round(avg(cycle_time_hours)::numeric, 2)                        AS avg_cycle_time_hours,
    round(avg(hub_processing_time_hours)::numeric, 2)               AS avg_hub_processing_hours,
    round(avg(csat_score)::numeric, 3)                              AS avg_csat
FROM gold.fct_orders
GROUP BY order_date, hub_id, hub_name;

CREATE OR REPLACE VIEW gold.kpi_hub_utilization_monthly AS
SELECT date_trunc('month', f.order_date)::date AS month, f.hub_id, f.hub_name,
       count(*) AS orders_created, h.hub_capacity_orders_per_month AS capacity,
       round(count(*)::numeric / h.hub_capacity_orders_per_month, 4) AS utilization
FROM gold.fct_orders f JOIN gold.dim_hub h USING (hub_id)
GROUP BY 1, f.hub_id, f.hub_name, h.hub_capacity_orders_per_month;

CREATE OR REPLACE VIEW gold.delay_reasons AS
SELECT date_trunc('month', order_date)::date AS month, hub_id, hub_name, delay_reason, count(*) AS delayed_orders
FROM gold.fct_orders WHERE is_delayed GROUP BY 1, 2, 3, 4;

CREATE OR REPLACE VIEW gold.driver_scorecard AS
SELECT d.driver_id, d.driver_name, d.employment_type, d.experience_years, d.performance_rating, d.home_hub_id,
       count(f.order_id) AS orders,
       count(*) FILTER (WHERE f.order_status = 'delivered') AS delivered,
       round((count(*) FILTER (WHERE f.is_on_time))::numeric / NULLIF(count(*) FILTER (WHERE f.order_status = 'delivered'), 0), 4) AS on_time_rate,
       round(avg(f.csat_score)::numeric, 3) AS avg_csat,
       round(avg(f.cycle_time_hours)::numeric, 2) AS avg_cycle_time_hours
FROM gold.dim_driver d LEFT JOIN gold.fct_orders f ON f.driver_id = d.driver_id
GROUP BY d.driver_id, d.driver_name, d.employment_type, d.experience_years, d.performance_rating, d.home_hub_id;

-- Transparent rule-based fleet risk score (45 vehicles is far too few for ML; see ADR-0005).
-- risk = 0.5 * percentile(breakdown rate per year of service) + 0.3 * maintenance_alert + 0.2 * percentile(age)
CREATE OR REPLACE VIEW gold.fleet_health AS
WITH base AS (
    SELECT v.*, GREATEST(((SELECT max(created_at)::date FROM silver.orders) - v.purchase_date) / 365.25, 0.5) AS age_years
    FROM gold.dim_vehicle v
), scored AS (
    SELECT b.*, b.breakdown_count_total / b.age_years AS breakdowns_per_year,
           percent_rank() OVER (ORDER BY b.breakdown_count_total / b.age_years) AS p_rate,
           percent_rank() OVER (ORDER BY b.age_years) AS p_age
    FROM base b
)
SELECT s.vehicle_id, s.vehicle_code, s.vehicle_model, s.vehicle_type, s.vehicle_status, s.home_hub_id,
       s.purchase_date, round(s.age_years::numeric, 1) AS age_years, s.breakdown_count_total,
       round(s.breakdowns_per_year::numeric, 2) AS breakdowns_per_year, s.maintenance_alert,
       round((0.5 * s.p_rate + 0.3 * s.maintenance_alert::int + 0.2 * s.p_age)::numeric, 3) AS risk_score,
       CASE WHEN 0.5 * s.p_rate + 0.3 * s.maintenance_alert::int + 0.2 * s.p_age >= 0.66 THEN 'High'
            WHEN 0.5 * s.p_rate + 0.3 * s.maintenance_alert::int + 0.2 * s.p_age >= 0.33 THEN 'Medium' ELSE 'Low' END AS risk_tier
FROM scored s;

CREATE OR REPLACE VIEW gold.live_orders_in_flight AS
SELECT f.order_id, f.hub_name, f.order_status, f.service_level, f.destination_city, f.driver_name, f.vehicle_code,
       f.created_at, f.dispatched_at,
       round((EXTRACT(EPOCH FROM ((SELECT sim_now FROM gold.sim_clock) - f.created_at)) / 3600.0)::numeric, 1) AS age_hours
FROM gold.fct_orders f
WHERE f.order_status IN ('created', 'at_hub', 'in_transit');

CREATE OR REPLACE VIEW gold.pipeline_health AS
SELECT date_trunc('minute', ingested_at) AS minute,
       count(*) AS events_ingested,
       round(avg(EXTRACT(EPOCH FROM (ingested_at - produced_at)))::numeric, 3) AS avg_latency_seconds,
       round(max(EXTRACT(EPOCH FROM (ingested_at - produced_at)))::numeric, 3) AS max_latency_seconds
FROM bronze.order_events GROUP BY 1;

CREATE OR REPLACE VIEW gold.ingest_summary AS
SELECT table_name, sum(received) AS received, sum(inserted) AS inserted, sum(duplicates) AS duplicates_dropped,
       (SELECT count(*) FROM bronze.dead_letter) AS dead_letters
FROM bronze.ingest_log GROUP BY table_name;

-- Statistical process control (p-chart) on the weekly delay rate per hub: flags *abnormal* weeks (3-sigma), not noise.
CREATE OR REPLACE VIEW gold.delay_control_chart_weekly AS
WITH weekly AS (
    SELECT hub_id, hub_name, date_trunc('week', order_date)::date AS week_start,
           count(*) FILTER (WHERE order_status = 'delivered') AS delivered,
           count(*) FILTER (WHERE is_delayed) AS delayed
    FROM gold.fct_orders GROUP BY 1, 2, 3
), centre AS (
    SELECT hub_id, sum(delayed)::float8 / NULLIF(sum(delivered), 0) AS p_bar FROM weekly GROUP BY hub_id
)
SELECT w.hub_id, w.hub_name, w.week_start, w.delivered, w.delayed,
       round((w.delayed::numeric / NULLIF(w.delivered, 0)), 4) AS delay_rate,
       round(c.p_bar::numeric, 4) AS centre_line,
       round(GREATEST(c.p_bar - 3 * sqrt(c.p_bar * (1 - c.p_bar) / NULLIF(w.delivered, 0)), 0)::numeric, 4) AS lcl,
       round(LEAST(c.p_bar + 3 * sqrt(c.p_bar * (1 - c.p_bar) / NULLIF(w.delivered, 0)), 1)::numeric, 4) AS ucl,
       (w.delayed::float8 / NULLIF(w.delivered, 0)) > c.p_bar + 3 * sqrt(c.p_bar * (1 - c.p_bar) / NULLIF(w.delivered, 0)) AS out_of_control
FROM weekly w JOIN centre c USING (hub_id);
