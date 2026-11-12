# Data dictionary & provenance

**Provenance classes** — `SOURCE` supplied file · `EXTERNAL` real public data · `DERIVED` computed from source · `SYNTHETIC` generated with fixed seed (42), deliberately *not* correlated with delays.

## Source tables (after Step 02 cleaning)
### Orders → `orders_enriched.csv` / `gold.fct_orders` (27,979 rows)
| Column | Class | Description |
|---|---|---|
| order_id | SOURCE | primary key |
| order_date | SOURCE | local order date |
| order_status | SOURCE | Delivered / Cancelled (warehouse: delivered / cancelled / in_transit / at_hub / created) |
| is_delayed | SOURCE, **corrected** | late delivery. Source flagged all 252 cancelled orders as delayed → corrected to *delivered-only* (R07a) |
| delay_reason | SOURCE | only when delayed (10 categories) |
| cancellation_reason | SOURCE (renamed) | the reason that the source stored in `Delay Reason` for cancelled orders |
| hub_id / driver_id / vehicle_id | SOURCE (keys) | FKs; names and codes were replaced by ids (R02) |
| hub_processing_time_hours | SOURCE | time at hub before dispatch |
| delivery_time_hours | SOURCE | transit time, dispatch → delivery (null if cancelled) |
| csat_score | SOURCE | 1-5; NULL for cancelled (source had placeholder 1, R07b) |
| source_delivery_date | SOURCE | kept for reconciliation |
| created_at, hub_received_at, dispatched_at, delivered_at, cancelled_at, feedback_at | DERIVED (UTC) | built from order_date + durations; **time-of-day is SYNTHETIC**. Honours the source delivery date for 92.3 % of orders; the rest conflict with the source's own hours (R08a) |
| destination_city, dest_lat, dest_lon, distance_km | SYNTHETIC | real Texas cities around each hub; road distance = 1.25 × straight line |
| service_level, package_weight_kg | SYNTHETIC | Standard/Express/Economy 70/20/10; log-normal weight |
| temp_c, precip_mm, wind_kmh, weather_code, is_severe_weather | EXTERNAL | Open-Meteo daily archive at hub coordinates. `weather_source` = `open-meteo` or **`synthetic_fallback`** (if the API was unreachable) |
| is_weekend, is_holiday | DERIVED/EXTERNAL | US + Texas holidays (`holidays` library) |
| vehicle_before_purchase, driver_before_hire | DERIVED flags | data-consistency flags (R09) |
| delivery_date_reconciled | DERIVED | timestamp-derived delivery date equals source date |

### Dimensions
| Table | Key | Notes |
|---|---|---|
| `dim_hub` | hub_id | 6 Texas hubs; `hub_capacity_orders_per_month` (**unit inferred**, ADR-0003); lat/lon/timezone EXTERNAL |
| `dim_driver` | driver_id | 55; `home_hub_id` derived (each driver serves one hub); names duplicate for 2 pairs — never join on name |
| `dim_vehicle` | vehicle_id | 45; `vehicle_type` from Orders (operational class) next to `vehicle_model`; 6 of 9 models appear under several types (R05); `vehicle_status`, `breakdown_count_total`, `maintenance_alert` are **current snapshots**, not history |
| `dim_date` | date | calendar 2023-01-01 → 2025-01-31 with holidays |
| `weather_daily` | hub_id, date | EXTERNAL (or flagged fallback) |

## Warehouse objects
| Object | Grain | Purpose |
|---|---|---|
| `bronze.order_events`, `bronze.vehicle_telemetry` | event | raw landing |
| `bronze.dead_letter`, `bronze.ingest_log` | message / batch | quality + throughput |
| `silver.orders` | order | state rebuilt from events |
| `silver.vehicle_latest_position` | vehicle | latest ping |
| `gold.fct_orders` | order | enriched fact |
| `gold.kpi_daily_hub` | hub × day | volume, on-time, cancellation, cycle time, CSAT |
| `gold.kpi_hub_utilization_monthly` | hub × month | orders ÷ capacity |
| `gold.delay_reasons` | hub × month × reason | |
| `gold.driver_scorecard` | driver | |
| `gold.fleet_health` | vehicle | rule-based risk score (ADR-0005) |
| `gold.delay_control_chart_weekly` | hub × week | p-chart limits (3σ) |
| `gold.live_orders_in_flight`, `gold.sim_clock` | order / 1 | live view |
| `gold.pipeline_health`, `gold.ingest_summary` | minute / table | latency, duplicates, dead letters |
| `gold.forecast_daily_hub`, `gold.ml_metrics` | hub × day / metric | ML outputs |

## Known limitations of the source
Uniform-looking delay causes (R13) · vehicle used before purchase date for 782 orders (R09a) · driver before hire date for 1,193 orders (R09b) ·
status snapshot of vehicles (R10) · only 2 years of history, ~38 orders/day network-wide.
