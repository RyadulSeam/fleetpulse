# Runbook

## 0. Prerequisites
Python 3.11+, Docker Desktop (for Postgres + Redpanda), Git. Internet access for step 03 (Open-Meteo) and `pip install`.
Windows: use **Git Bash** (matches the project's conventions); activate the venv with `source .venv/Scripts/activate`.

## 1. First-time setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d && docker compose ps          # postgres healthy, redpanda running
```
Put the four original files in `data/raw/` (already there): `Orders.csv Drivers.csv Hubs.csv Vehicles.csv`.

## 2. Run order (each command is idempotent, safe to repeat)
| Step | Command | Verify |
|---|---|---|
| 01 | `python pipeline/01_convert_and_profile.py` | `reports/dq/01_raw_profile.md` exists; `data/interim/*.csv` UTF-8 |
| 02 | `python pipeline/02_clean_standardize.py` | log shows 24 rules; `reports/dq/02_data_quality_report.md` |
| 03 | `python pipeline/03_enrich.py` (add `--require-real-weather` to forbid fallback) | log: `Weather source mix: {'open-meteo': 27979}` |
| 04+05 backfill | `python pipeline/04_replay_stream.py --mode backfill --sink kafka` then `python pipeline/05_consume_to_postgres.py --source kafka --exit-when-idle 20` | `inserted ≈ 138.6k`, `dead_letter=0` |
| 06 | `python pipeline/06_build_warehouse.py` | `bronze.order_events rows: …` |
| 07 | `python pipeline/07_run_dq_checks.py` | `0 blocking failures` (exit code 0) |
| 08 | `python pipeline/08_train_models.py` | `reports/ml/model_card.md` |
| 09 | `python pipeline/09_forecast_demand.py` | `gold.forecast_daily_hub` has 84 rows |

## 3. Go live
Terminal A: `python pipeline/05_consume_to_postgres.py --source kafka`
Terminal B: `python pipeline/04_replay_stream.py --mode live --sink kafka --speed 3600` (≈ 7 simulated days in ~3 minutes; use `--speed 600` for slower)
Terminal C: `streamlit run services/dashboard/app.py` → http://localhost:8501 · API: `uvicorn services.api.main:app --port 8000` → http://localhost:8000/docs
Watch topics in Redpanda Console: http://localhost:8080.
*Note:* the backfill excludes the live window, so the first live run delivers genuinely new events and the dashboard moves. Replaying the same window again inserts 0 rows (idempotency); to watch it again from a clean start run `docker compose down -v`, then backfill, then live.

## 4. Reset
`docker compose down -v` wipes Postgres + Redpanda. Re-run from step 04. Steps 01–03 outputs are kept in `data/`.

## 5. Troubleshooting
| Symptom | Cause / fix |
|---|---|
| `UnicodeDecodeError … 0xff` | raw CSV is UTF-16: always start with step 01 |
| step 03 log says `synthetic_fallback` | no internet / API blocked. Re-run with internet; cached synthetic files are auto-refreshed |
| `NoBrokersAvailable` / timeout on kafka | `docker compose ps`; bootstrap must be `localhost:19092` (host), not `redpanda:9092` |
| consumer shows `duplicates_dropped > 0` | expected (0.5 % injected duplicates + any replay) |
| DQ `C13` warn | backfill/live not fully loaded yet |
| dashboard shows "Data not available" | run steps 05–06 first; check `.env` DB credentials |
| `ModuleNotFoundError: fleetpulse` | run scripts from repo root (they add `src/` themselves); for pytest `pytest.ini` handles it |
| GitHub images broken in README | file names are case-sensitive and must not contain spaces; on Windows Git Bash avoid merge conflicts by pulling before push |

## 6. Operations notes
Consumer lag, latency and duplicates are visible in the dashboard's *Pipeline health* tab (`gold.pipeline_health`, `gold.ingest_summary`).
Alert candidates (not wired): dead_letter > 0, avg latency > 60 s, DQ gate exit code ≠ 0.
