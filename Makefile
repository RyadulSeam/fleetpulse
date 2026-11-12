.PHONY: setup up down offline backfill live consume warehouse dq ml forecast test lint api dashboard all
PY ?= python

setup:            ## create venv + install deps (Linux/macOS: source .venv/bin/activate afterwards)
	python -m venv .venv && .venv/bin/pip install -r requirements.txt
up:               ## start Postgres + Redpanda + Console
	docker compose up -d
down:
	docker compose down

# ---- steps 01-03: batch preparation (no infrastructure needed) ----
offline:
	$(PY) pipeline/01_convert_and_profile.py
	$(PY) pipeline/02_clean_standardize.py
	$(PY) pipeline/03_enrich.py

# ---- steps 04-07: streaming + warehouse (needs `make up`) ----
backfill:         ## produce history, then drain it into bronze
	$(PY) pipeline/04_replay_stream.py --mode backfill --sink kafka
	$(PY) pipeline/05_consume_to_postgres.py --source kafka --exit-when-idle 20
warehouse:
	$(PY) pipeline/06_build_warehouse.py
live:             ## run in TWO terminals: `make consume` then `make live`
	$(PY) pipeline/04_replay_stream.py --mode live --sink kafka --speed 3600
consume:
	$(PY) pipeline/05_consume_to_postgres.py --source kafka
dq:
	$(PY) pipeline/07_run_dq_checks.py

# ---- steps 08-09: ML ----
ml:
	$(PY) pipeline/08_train_models.py
forecast:
	$(PY) pipeline/09_forecast_demand.py

test:
	$(PY) -m pytest -q
lint:
	ruff check .
api:
	uvicorn services.api.main:app --port 8000
dashboard:
	streamlit run services/dashboard/app.py
