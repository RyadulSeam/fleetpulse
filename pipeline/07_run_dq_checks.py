"""STEP 07 – Warehouse data-quality gate. Executable assertions over bronze/silver/gold.

Every check is a SQL query returning the NUMBER OF VIOLATING ROWS (0 = pass). Severity:
  error -> pipeline must stop / alert (exit code 1)       warn -> investigate, does not block
Run after every load (and in CI against a fixture database). Results are written to reports/dq/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fleetpulse.common import get_logger, path, pg_connect  # noqa: E402

log = get_logger("step07")

CHECKS = [
    ("C01", "error", "Every order has an order_created event", "SELECT count(*) FROM silver.orders WHERE created_at IS NULL"),
    ("C02", "error", "No order has more than 6 events (one per event type)", "SELECT count(*) FROM silver.orders WHERE event_count > 6"),
    ("C03", "error", "Timeline order: created <= hub_received <= dispatched <= delivered",
     """SELECT count(*) FROM silver.orders WHERE hub_received_at < created_at OR dispatched_at < hub_received_at OR delivered_at < dispatched_at"""),
    ("C04", "error", "Orders resolve to hub, driver and vehicle dimensions",
     "SELECT count(*) FROM gold.fct_orders WHERE hub_name IS NULL OR driver_name IS NULL OR vehicle_code IS NULL"),
    ("C05", "error", "Delivered orders carry an is_delayed flag", "SELECT count(*) FROM silver.orders WHERE order_status='delivered' AND is_delayed IS NULL"),
    ("C06", "error", "delay_reason present if and only if delayed",
     "SELECT count(*) FROM silver.orders WHERE (is_delayed IS TRUE AND delay_reason IS NULL) OR (COALESCE(is_delayed,false) IS FALSE AND delay_reason IS NOT NULL)"),
    ("C07", "error", "Cancelled orders are never 'delayed' and have no CSAT",
     "SELECT count(*) FROM silver.orders WHERE order_status='cancelled' AND (is_delayed IS TRUE OR csat_score IS NOT NULL)"),
    ("C08", "error", "CSAT within 1-5", "SELECT count(*) FROM silver.orders WHERE csat_score IS NOT NULL AND csat_score NOT BETWEEN 1 AND 5"),
    ("C09", "error", "Telemetry coordinates/fuel/speed within valid ranges",
     "SELECT count(*) FROM bronze.vehicle_telemetry WHERE lat NOT BETWEEN 25 AND 37 OR lon NOT BETWEEN -107 AND -93 OR fuel_pct NOT BETWEEN 0 AND 100 OR speed_kmh < 0"),
    ("C10", "warn", "No dead-letter messages", "SELECT count(*) FROM bronze.dead_letter"),
    ("C11", "warn", "Stuck orders (not finished 10+ sim-days after creation)",
     "SELECT count(*) FROM silver.orders o, gold.sim_clock c WHERE o.order_status NOT IN ('delivered','cancelled') AND o.created_at < c.sim_now - interval '10 days'"),
    ("C12", "warn", "Ingestion latency under 60s (producer -> bronze) for live events",
     "SELECT count(*) FROM bronze.order_events WHERE event_time >= (SELECT max(event_time) - interval '3 days' FROM bronze.order_events) AND ingested_at - produced_at > interval '60 seconds'"),
    ("C13", "warn", "Warehouse order count equals source order count (see detail)", None),
]


def main() -> int:
    conn = pg_connect()
    results, failed_error = [], 0
    with conn.cursor() as cur:
        for cid, sev, title, sql in CHECKS:
            if sql is None:
                src = path("processed") / "orders_enriched.csv"
                cur.execute("SELECT count(*) FROM silver.orders")
                wh = cur.fetchone()[0]
                exp = len(pd.read_csv(src, usecols=["order_id"])) if src.exists() else wh
                viol = abs(exp - wh)
                detail = f"warehouse={wh:,} source={exp:,}"
            else:
                cur.execute(sql)
                viol, detail = cur.fetchone()[0], ""
            status = "PASS" if viol == 0 else ("FAIL" if sev == "error" else "WARN")
            failed_error += status == "FAIL"
            results.append({"id": cid, "severity": sev, "check": title, "violations": int(viol), "status": status, "detail": detail})
            log.info("%s %-4s %s -> %s %s", cid, status, title, viol, detail)
    conn.close()

    rep = path("reports_dq")
    (rep / "07_pipeline_dq_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    md = ["# Step 07 – Warehouse data-quality gate", "", "| ID | Status | Severity | Check | Violations | Detail |", "|---|---|---|---|---:|---|"]
    md += [f"| {r['id']} | {r['status']} | {r['severity']} | {r['check']} | {r['violations']:,} | {r['detail']} |" for r in results]
    (rep / "07_pipeline_dq_results.md").write_text("\n".join(md), encoding="utf-8")
    log.info("%s blocking failures", failed_error)
    return 1 if failed_error else 0


if __name__ == "__main__":
    sys.exit(main())
