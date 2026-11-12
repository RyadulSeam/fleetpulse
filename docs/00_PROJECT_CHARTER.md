# Project charter

| | |
|---|---|
| **Project** | FleetPulse – Real-Time Logistics Intelligence Platform |
| **Owner** | Ryadul Seam, Seam Analytics |
| **Audience** | Operations Managers / Directors in logistics, supply chain and retail distribution; hiring managers reviewing a portfolio |
| **Cost** | 0 USD: Docker, PostgreSQL, Redpanda, Python, Streamlit, Open-Meteo (all free; Power BI Desktop is free) |

## Business problem
A regional carrier runs 6 hubs, 55 drivers and 45 vehicles in Texas. Managers lack (1) a live view of orders and fleet,
(2) trustworthy KPIs (delays, utilisation, driver and fleet performance) and (3) forward-looking demand and risk signals.

## Objectives and success criteria
| # | Objective | Success criterion | Status |
|---|---|---|---|
| 1 | Live operational view | Event → dashboard latency < 10 s in replay at 3600× | Built; latency to be measured in your Kafka run (Pipeline Health tab) |
| 2 | Trusted KPIs | Warehouse totals reconcile 100 % to source | ✅ verified |
| 3 | Data quality gate | All blocking checks pass on every load | ✅ 13/13 |
| 4 | Predictive value | Delay model with AUC lower bound > 0.55 | ❌ not achievable on this data (reported) |
| 5 | Demand forecast | Beats seasonal-naive on backtest | ✅ (modest) |
| 6 | Reproducibility | One command infra; CI green | ✅ |

## Scope
**In:** ingestion, modelling, quality, ML, forecasting, live dashboard, API, documentation.
**Out (phase 2):** Power BI analytical dashboards. **Out (not planned):** driver-level automated decisions.

## Principles
1. Honesty over impressiveness: every synthetic element is labelled; failures are reported.
2. Idempotence and replayability everywhere.
3. One source of truth per metric (`docs/07_KPI_DEFINITIONS.md`).
4. Every step has an input, an output, a way to verify it, and a document.
