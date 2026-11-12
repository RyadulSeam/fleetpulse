# Conclusion summary — technical

## Outcome
| Layer | Result |
|---|---|
| Ingestion | UTF-16 → UTF-8; 24-rule source audit; every correction logged (reports/dq/02) |
| Streaming | Redpanda/Kafka topics, deterministic event IDs, injected duplicates (0.5 %) & late events (1 %), idempotent consumer, dead-letter, offsets after commit; replaying a file twice inserts 0 rows |
| Warehouse | bronze → silver (views, order state rebuilt from events) → gold (13 marts/views); totals reconcile exactly to source (27,727 delivered / 5,656 delayed / 22,071 on-time / CSAT 4.197 / 35.78 h) |
| Quality gate | 13 SQL assertions, 13/13 PASS, exit-code gated |
| ML | Delay AUC 0.499 [0.476, 0.523] (LR) / 0.493 (LightGBM) vs threshold 0.55 → **no reliable signal**; ETA MAE 18.65 h vs 18.68 h baseline; 0/10 segmentation dimensions significant (Bonferroni) |
| Forecast | 6-fold rolling-origin backtest WAPE: LightGBM 0.314 < seasonal-naive 0.336 < MA-28 0.382 → LightGBM selected, 80 % intervals from residuals |
| Serving | FastAPI `/predict` (always returns reliability status), `/forecast/{hub}`; Streamlit live dashboard (4 tabs) |
| Engineering | 22 tests (unit, contract, integration, dashboard smoke), ruff clean, GitHub Actions pipeline |

## Decisions worth defending (ADRs in docs/adr)
Replay-simulated real-time (0001) · SQL views over dbt for now (0002) · capacity unit inferred as orders/month (0003) · master-table authority (0004) · rule-based fleet risk (0005) · pre-registered ML verdict (0006) · Redpanda (0007).

## Defects found by the controls (now regression-tested)
DST fall-back hour dropped 11 orders; `csat_score` emitted as float broke integer casts; live window contained no new orders; cancelled events lacked driver/vehicle.

## Honest limitations
Replay, not live. Synthetic: event time-of-day, destinations, distance, weight, service level, telemetry. Weather is real only when Open-Meteo was reachable (reference run used the flagged fallback; re-run regenerates reports). Capacity unit assumed. Kafka path is written for Docker/Redpanda; offline CI exercises identical validation and insert code through the JSONL source.

## Next
Phase 2: Power BI (docs/08). Optional: Grafana ops board, dbt, containerised services, orchestration, alert wiring on DQ/latency.
