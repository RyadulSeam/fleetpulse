"""STEP 02 – Clean, standardise and validate (with a documented data-quality rule log).

Principles
  * Never silently "fix" data: every rule is logged with a count, severity and the decision taken.
  * Master tables (Drivers, Vehicles, Hubs) are the source of truth; Orders keeps foreign keys only.
  * Raw files are never modified; cleaned output is written to data/interim/clean_*.csv.

Input : data/interim/{Orders,Drivers,Hubs,Vehicles}.csv   (from Step 01)
Output: data/interim/clean_{orders,drivers,hubs,vehicles}.csv
        reports/dq/02_dq_rules.json / 02_data_quality_report.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fleetpulse.common import get_logger, load_config, path  # noqa: E402

log = get_logger("step02")
RULES: list[dict] = []


def rule(rid: str, title: str, severity: str, affected: int, total: int, decision: str, detail: str = "") -> None:
    RULES.append({"id": rid, "title": title, "severity": severity, "affected": int(affected), "total": int(total),
                  "pct": round(100 * affected / total, 2) if total else 0.0, "decision": decision, "detail": detail})
    log.info("%s [%s] %s -> %s/%s | %s", rid, severity, title, affected, total, decision)


def snake(cols):
    return [c.strip().lower().replace(" ", "_") for c in cols]


def main() -> None:
    cfg = load_config()
    fmt = cfg["source_dates"]["format"]
    src, out = path("interim"), path("interim")

    orders, drivers = pd.read_csv(src / "Orders.csv"), pd.read_csv(src / "Drivers.csv")
    hubs, vehicles = pd.read_csv(src / "Hubs.csv"), pd.read_csv(src / "Vehicles.csv")
    n = len(orders)

    # ---------- Hubs ----------
    hubs = hubs.rename(columns={"Hub ID": "hub_id", "HubName": "hub_name", "Hub Capacity": "hub_capacity_orders_per_month"})
    # ---------- Drivers ----------
    drivers = drivers.rename(columns={"DriverID": "driver_id", "DriverName": "driver_name", "Employment Type": "employment_type",
                                      "Hire Date": "hire_date", "Experience Years": "experience_years", "Performance Rating": "performance_rating"})
    drivers["hire_date"] = pd.to_datetime(drivers["hire_date"], format=fmt)
    # ---------- Vehicles ----------
    vehicles = vehicles.rename(columns={"Purchase Date": "purchase_date", "Vehicle ID": "vehicle_id", "Vehicle Model": "vehicle_model",
                                        "Vehicle Status": "vehicle_status", "Breakdown": "breakdown_count_total",
                                        "Maintenance count Alert": "maintenance_alert", "Vehicle Code": "vehicle_code"})
    vehicles["purchase_date"] = pd.to_datetime(vehicles["purchase_date"], format=fmt)
    vehicles["maintenance_alert"] = vehicles["maintenance_alert"].astype(bool)
    # ---------- Orders (rename + parse) ----------
    orders.columns = snake(orders.columns)
    orders = orders.rename(columns={"actual_delivery_date": "source_delivery_date", "driver_name": "source_driver_name",
                                    "is_delayed": "is_delayed_source", "vehicle_name": "vehicle_code",
                                    "vehicle_type": "source_vehicle_type", "customer_satisfaction_score": "csat_score"})
    orders["order_date"] = pd.to_datetime(orders["order_date"], format=fmt)
    orders["source_delivery_date"] = pd.to_datetime(orders["source_delivery_date"], format=fmt)

    # ================= RULES =================
    # R01 primary keys
    for name, df, k in [("orders", orders, "order_id"), ("drivers", drivers, "driver_id"), ("vehicles", vehicles, "vehicle_id"), ("hubs", hubs, "hub_id")]:
        rule(f"R01-{name}", f"Primary key `{k}` unique", "error", df[k].duplicated().sum(), len(df), "none needed" if not df[k].duplicated().any() else "STOP")

    # R02 foreign keys (map names/codes to surrogate ids)
    hub_map = dict(zip(hubs.hub_name, hubs.hub_id))
    veh_map = dict(zip(vehicles.vehicle_code, vehicles.vehicle_id))
    orders["hub_id"] = orders["hub_name"].map(hub_map)
    orders["vehicle_id"] = orders["vehicle_code"].map(veh_map)
    rule("R02-hub", "Orders.hub_name resolves to Hubs", "error", orders.hub_id.isna().sum(), n, "replaced hub_name with hub_id")
    rule("R02-vehicle", "Orders.vehicle_code resolves to Vehicles", "error", orders.vehicle_id.isna().sum(), n, "replaced vehicle_code with vehicle_id")
    rule("R02-driver", "Orders.driver_id exists in Drivers", "error", (~orders.driver_id.isin(drivers.driver_id)).sum(), n, "kept driver_id as FK")

    # R03 driver-name conflict
    dn = drivers.set_index("driver_id").driver_name
    mism = (orders.driver_id.map(dn) != orders.source_driver_name).sum()
    rule("R03", "Orders.Driver Name disagrees with Drivers master for the same Driver ID", "error", mism, n,
         "Drivers master is authoritative; Orders.driver_name dropped (denormalised copy was unreliable)",
         "Every Driver ID carries exactly one name in Orders, but it differs from the master name for all IDs.")
    dup_names = drivers[drivers.driver_name.duplicated(keep=False)]
    rule("R04", "Duplicate driver names in Drivers (different IDs)", "warn", len(dup_names), len(drivers),
         "names are never used as keys; always join on driver_id", ", ".join(sorted(dup_names.driver_name.unique())))

    # R05 vehicle type vs model
    veh_type = orders.groupby("vehicle_code").source_vehicle_type.agg(lambda s: s.mode().iat[0])
    vehicles["vehicle_type"] = vehicles.vehicle_code.map(veh_type).fillna("Unassigned")
    mt = vehicles[vehicles.vehicle_type != "Unassigned"].groupby("vehicle_model").vehicle_type.nunique()
    rule("R05", "Same vehicle model appears under several vehicle types", "warn", int((mt > 1).sum()), len(mt),
         "vehicle_type (operational class from Orders) moved to Vehicles dim next to vehicle_model; both kept, conflict documented",
         "Models affected: " + ", ".join(mt[mt > 1].index))
    rule("R05b", "Vehicles never used in any order", "info", (vehicles.vehicle_type == "Unassigned").sum(), len(vehicles),
         "kept in dim as 'Unassigned' (spare fleet)")

    # home hub of drivers / vehicles (each maps to exactly one hub in the data)
    for dim, key, col in [(drivers, "driver_id", "home_hub_id"), (vehicles, "vehicle_id", "home_hub_id")]:
        hh = orders.groupby(key).hub_id.agg(lambda s: s.mode().iat[0])
        dim[col] = dim[key].map(hh).astype("Int64")
    multi = (orders.groupby("driver_id").hub_id.nunique() > 1).sum() + (orders.groupby("vehicle_id").hub_id.nunique() > 1).sum()
    rule("R06", "Drivers/vehicles working for more than one hub", "info", multi, len(drivers) + len(vehicles), "home_hub_id = modal hub (data shows 1:1)")

    # R07 cancelled orders
    canc = orders.order_status.eq("Cancelled")
    rule("R07a", "Cancelled orders flagged Is Delayed=True", "error", (canc & orders.is_delayed_source).sum(), canc.sum(),
         "is_delayed recomputed: delay only applies to Delivered orders")
    rule("R07b", "Cancelled orders carrying CSAT=1 placeholder", "error", (canc & orders.csat_score.eq(1)).sum(), canc.sum(),
         "csat_score set to NULL for cancelled orders (no survey exists)")
    orders["is_delayed"] = orders.is_delayed_source & ~canc
    orders["cancellation_reason"] = orders.delay_reason.where(canc)
    orders["delay_reason"] = orders.delay_reason.where(orders.is_delayed)
    orders["csat_score"] = orders.csat_score.where(~canc).astype("Int64")
    orders["is_cancelled"] = canc

    # R08 date reconciliation (delivered)
    dl = orders[~canc].copy()
    tot = dl.hub_processing_time_hours + dl.delivery_time_hours
    calc_days = np.floor(tot / 24)
    days = (dl.source_delivery_date - dl.order_date).dt.days
    rule("R08a", "Delivery date != order date + floor((processing+delivery hours)/24)", "warn", (days != calc_days).sum(), len(dl),
         "hours are treated as the authoritative duration; Step 03 builds timestamps so dates reconcile wherever feasible",
         f"within +-1 day: {((days - calc_days).abs() <= 1).mean():.1%}")
    rule("R08b", "Delivery before order", "error", (days < 0).sum(), len(dl), "none needed")

    # R09 vehicle used before purchase / driver before hire
    pdate = orders.vehicle_id.map(vehicles.set_index("vehicle_id").purchase_date)
    hdate = orders.driver_id.map(drivers.set_index("driver_id").hire_date)
    early_v, early_d = orders.order_date < pdate, orders.order_date < hdate
    rule("R09a", "Order served by a vehicle before its purchase date", "warn", early_v.sum(), n,
         "kept; flagged as `vehicle_before_purchase`. Dim dates treated as registry dates, not in-service dates",
         f"{orders[early_v].vehicle_id.nunique()} vehicles involved")
    rule("R09b", "Order served by a driver before hire date", "warn", early_d.sum(), n, "kept; flagged as `driver_before_hire`")
    orders["vehicle_before_purchase"], orders["driver_before_hire"] = early_v, early_d

    # R10 status snapshot
    rule("R10", "Orders served by vehicles whose *current* status is 'Maintenance'", "info",
         orders.vehicle_id.map(vehicles.set_index("vehicle_id").vehicle_status).eq("Maintenance").sum(), n,
         "Vehicle Status is a point-in-time snapshot, not history; never used as a historical filter")

    # R11 ranges
    rule("R11a", "csat_score outside 1-5", "error", (~orders.csat_score.dropna().between(1, 5)).sum(), n, "none needed")
    rule("R11b", "non-positive durations", "error", ((orders.hub_processing_time_hours <= 0) | (orders.delivery_time_hours <= 0)).sum(), n, "none needed")
    rule("R11c", "Missing delivery hours on delivered orders", "error", (orders.delivery_time_hours.isna() & ~canc).sum(), n, "none needed")

    # R12 hub capacity unit inference
    monthly = orders.groupby(["hub_id", orders.order_date.dt.to_period("M")]).size().groupby("hub_id").mean()
    util = (monthly / hubs.set_index("hub_id").hub_capacity_orders_per_month).round(3)
    rule("R12", "Hub Capacity unit undocumented", "warn", len(hubs), len(hubs),
         "assumed orders/month (ADR-0003). Mean monthly utilisation: " + ", ".join(f"hub {h}: {u:.0%}" for h, u in util.items()))

    # R13 statistical shape (is there structure to learn?)
    reasons = orders.delay_reason.value_counts()
    chi_r = stats.chisquare(reasons.values)
    ct = pd.crosstab(orders[~canc].hub_id, orders[~canc].is_delayed)
    chi_h = stats.chi2_contingency(ct)
    rule("R13", "Delay reasons are near-uniformly distributed", "info", 0, 1,
         "No action. Expect weak predictive signal; modelling step must report this honestly",
         f"chi-square uniformity p={chi_r.pvalue:.3f}; share range {reasons.min() / reasons.sum():.1%}-{reasons.max() / reasons.sum():.1%}. "
         f"Delay rate vs hub: chi-square p={chi_h[1]:.3f}")

    # ---------- finalise orders ----------
    keep = ["order_id", "order_date", "order_status", "is_cancelled", "is_delayed", "delay_reason", "cancellation_reason",
            "hub_id", "driver_id", "vehicle_id", "hub_processing_time_hours", "delivery_time_hours", "csat_score",
            "source_delivery_date", "vehicle_before_purchase", "driver_before_hire"]
    orders = orders[keep].sort_values("order_id")
    orders.to_csv(out / "clean_orders.csv", index=False)
    drivers.to_csv(out / "clean_drivers.csv", index=False)
    vehicles.to_csv(out / "clean_vehicles.csv", index=False)
    hubs.to_csv(out / "clean_hubs.csv", index=False)

    rep = path("reports_dq")
    (rep / "02_dq_rules.json").write_text(json.dumps(RULES, indent=2), encoding="utf-8")
    md = ["# Step 02 – Data quality report", "",
          f"Orders analysed: **{n:,}** · Rules evaluated: **{len(RULES)}**", "",
          "| ID | Severity | Rule | Affected | % | Decision |", "|---|---|---|---:|---:|---|"]
    for r in RULES:
        md.append(f"| {r['id']} | {r['severity']} | {r['title']} | {r['affected']:,} | {r['pct']} | {r['decision']} |")
    md += ["", "## Details", ""] + [f"- **{r['id']}** – {r['detail']}" for r in RULES if r["detail"]]
    (rep / "02_data_quality_report.md").write_text("\n".join(md), encoding="utf-8")
    log.info("Clean tables written. Orders=%s Drivers=%s Vehicles=%s Hubs=%s", len(orders), len(drivers), len(vehicles), len(hubs))


if __name__ == "__main__":
    main()
