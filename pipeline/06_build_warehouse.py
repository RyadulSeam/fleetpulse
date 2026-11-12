"""STEP 06 – Build the warehouse: DDL, dimension load, silver + gold views. Fully idempotent (safe to re-run any time).

Input : sql/*.sql, data/processed/dim_*.csv, weather_daily.csv
Output: PostgreSQL schemas bronze / silver / gold
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fleetpulse.common import ROOT, get_logger, path, pg_connect  # noqa: E402
from fleetpulse.ingest import apply_sql  # noqa: E402

log = get_logger("step06")

DIMS = {  # table -> (csv, ordered columns)
    "gold.dim_hub": ("dim_hub.csv", ["hub_id", "hub_name", "hub_capacity_orders_per_month", "lat", "lon", "timezone"]),
    "gold.dim_driver": ("dim_driver.csv", ["driver_id", "driver_name", "employment_type", "hire_date", "experience_years", "performance_rating", "home_hub_id"]),
    "gold.dim_vehicle": ("dim_vehicle.csv", ["vehicle_id", "purchase_date", "vehicle_model", "vehicle_status", "breakdown_count_total",
                                             "maintenance_alert", "vehicle_code", "vehicle_type", "home_hub_id"]),
    "gold.dim_date": ("dim_date.csv", ["date", "year", "quarter", "month", "month_name", "iso_week", "day_of_week", "day_name", "is_weekend", "is_holiday", "holiday_name"]),
    "gold.weather_daily": ("weather_daily.csv", ["hub_id", "date", "temp_c", "precip_mm", "wind_kmh", "weather_code", "weather_source", "is_severe_weather"]),
}


def load_dim(cur, table: str, csv: str, cols: list[str]) -> int:
    df = pd.read_csv(path("processed") / csv)[cols]
    for c in df.columns:
        if str(df[c].dtype) == "float64" and c.endswith(("_id", "_years", "_rating", "_total", "_code")):
            df[c] = df[c].astype("Int64")
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False)
    buf.seek(0)
    cur.execute(f"TRUNCATE {table}")
    cur.copy_expert(f"COPY {table} ({', '.join(cols)}) FROM STDIN WITH (FORMAT csv)", buf)
    return len(df)


def main() -> None:
    conn = pg_connect()
    sql = ROOT / "sql"
    apply_sql(conn, [sql / "00_schemas.sql", sql / "01_bronze.sql", sql / "02_dims.sql"])
    with conn, conn.cursor() as cur:
        for table, (csv, cols) in DIMS.items():
            log.info("loaded %s rows into %s", load_dim(cur, table, csv, cols), table)
    apply_sql(conn, [sql / "03_silver.sql", sql / "04_gold.sql"])
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM bronze.order_events")
        log.info("silver/gold views ready (bronze.order_events rows: %s)", cur.fetchone()[0])
    conn.close()


if __name__ == "__main__":
    main()
