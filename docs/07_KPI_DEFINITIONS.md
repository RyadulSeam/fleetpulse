# KPI definitions (single source of truth)

All KPIs are computed in `sql/04_gold.sql`; Power BI must reuse these views/measures, never re-derive them differently.

| KPI | Definition | Grain / notes |
|---|---|---|
| Orders created | count of orders with an `order_created` event | by local order date at the hub's timezone |
| Delivered / Cancelled | orders whose furthest state is `delivered` / `cancelled` | cohort by creation date |
| **On-time rate** | delivered orders with `is_delayed = false` ÷ delivered orders | cancelled orders excluded from numerator **and** denominator |
| Delay rate | delayed ÷ delivered | = 1 − on-time rate |
| Cancellation rate | cancelled ÷ created | |
| Cycle time (h) | `delivered_at − created_at` | includes hub receive lag + processing + transit |
| Hub processing (h) / Transit (h) | source durations | `hub_processing_time_hours`, `delivery_time_hours` |
| CSAT | mean `csat_score` of delivered orders with feedback | 1-5 |
| **Hub utilisation** | orders created in month ÷ `hub_capacity_orders_per_month` | capacity unit inferred (ADR-0003); >100 % = over capacity |
| In flight | orders with status created / at_hub / in_transit | uses the simulated clock |
| Driver on-time rate | on-time ÷ delivered per driver | only compare drivers with ≥ 100 deliveries |
| Fleet risk score | 0.5·pct_rank(breakdowns per year of service) + 0.3·maintenance_alert + 0.2·pct_rank(age) | tiers: High ≥ 0.66, Medium ≥ 0.33 — a transparent heuristic, **not** a model |
| Control-chart flag | weekly delay rate above p̄ + 3·√(p̄(1−p̄)/n) | expect ~0.3 % false alarms by chance alone |
| WAPE | Σ|forecast − actual| ÷ Σ actual | lower is better |
