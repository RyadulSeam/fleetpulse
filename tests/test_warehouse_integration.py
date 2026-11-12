import pytest

pytestmark = pytest.mark.integration


def scalar(pg, sql):
    with pg.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()[0]


def test_bronze_is_idempotent_by_event_id(pg):
    assert scalar(pg, "SELECT count(*) - count(DISTINCT event_id) FROM bronze.order_events") == 0


def test_silver_has_one_row_per_order(pg):
    assert scalar(pg, "SELECT count(*) - count(DISTINCT order_id) FROM silver.orders") == 0


def test_gold_kpis_reconcile_with_source_totals(pg):
    # Source file totals (Orders.csv): 27,727 delivered, 5,656 delayed, 22,071 on-time, 252 cancelled
    row = None
    with pg.cursor() as cur:
        cur.execute("SELECT count(*) FILTER (WHERE order_status='delivered'), count(*) FILTER (WHERE is_delayed), "
                    "count(*) FILTER (WHERE is_on_time), count(*) FILTER (WHERE order_status='cancelled') FROM gold.fct_orders")
        row = cur.fetchone()
    if row[0] + row[3] < 27979:
        pytest.skip("full dataset not loaded")
    assert row == (27727, 5656, 22071, 252)


def test_dq_gate_passes(pg):
    import importlib.util
    import pathlib

    spec = importlib.util.spec_from_file_location("dq", pathlib.Path(__file__).resolve().parents[1] / "pipeline" / "07_run_dq_checks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main() == 0
