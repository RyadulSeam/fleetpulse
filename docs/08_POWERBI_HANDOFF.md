# Power BI hand-off (Phase 2 — not yet built)

Everything upstream is finished. Power BI only needs to **connect and visualise**; no business logic belongs in DAX beyond formatting.

## Connection
Get Data → PostgreSQL → server `localhost`, database `fleetpulse` → Import mode (DirectQuery optional) → tables from schema **gold**.
Streaming tiles in the Power BI *service* usually require a paid licence — keep the live view in Streamlit, use Power BI for analysis (see charter).

## Tables to import
`gold.fct_orders` · `gold.kpi_daily_hub` · `gold.kpi_hub_utilization_monthly` · `gold.delay_reasons` · `gold.driver_scorecard` · `gold.fleet_health` ·
`gold.delay_control_chart_weekly` · `gold.forecast_daily_hub` · `gold.dim_hub` · `gold.dim_driver` · `gold.dim_vehicle` · `gold.dim_date`

Model: star schema around `fct_orders` (hub_id, driver_id, vehicle_id, order_date → `dim_date.date`). Mark `dim_date` as date table.

## Suggested pages (audience: operations managers)
1. **Executive overview** — on-time %, volume, cancellation %, CSAT, trend 2023–24.
2. **Hub performance & capacity** — utilisation vs 100 % line (Dallas), cycle time, processing time.
3. **Delay analysis** — reasons, CSAT impact of delay (3.02 vs 4.50), weekly control chart. *Show that causes are evenly spread — that is the finding.*
4. **Drivers & fleet** — scorecard (≥ 100 deliveries), fleet risk tiers, breakdowns.
5. **Demand forecast** — 14-day forecast with 80 % band per hub, backtest WAPE.
6. **Data & model transparency** — provenance (real/synthetic), DQ results, model card verdict.

## Rules
- Use definitions from `docs/07_KPI_DEFINITIONS.md` only. Design in Figma first (project convention), then rebuild in Power BI. Do not publish the `.pbix`.
- Label synthetic fields (destination, weight, service level, telemetry) wherever shown.
