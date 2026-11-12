import pytest


@pytest.fixture(scope="session")
def pg():
    psycopg2 = pytest.importorskip("psycopg2")
    from fleetpulse.common import pg_dsn

    try:
        conn = psycopg2.connect(**pg_dsn(), connect_timeout=3)
    except Exception:
        pytest.skip("PostgreSQL not available")
    yield conn
    conn.close()
