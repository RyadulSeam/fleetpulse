"""Small helpers shared by training, the API and the dashboard."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import OrdinalEncoder

from .features import CAT, FEATURES


class FittedModel:
    """Preprocessor + estimator bundled into one picklable object (so the API needs no training code)."""

    def __init__(self, estimator, name: str, task: str):
        self.estimator, self.name, self.task = estimator, name, task
        self.encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)

    def _x(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        x = df[FEATURES].copy()
        x[CAT] = (self.encoder.fit_transform(x[CAT].astype(str)) if fit else self.encoder.transform(x[CAT].astype(str)))
        return x.astype(float)

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        x = self._x(df)
        return self.estimator.predict_proba(x)[:, 1] if self.task == "classification" else self.estimator.predict(x)


def bootstrap_auc_ci(y: np.ndarray, p: np.ndarray, n: int = 500, seed: int = 42) -> tuple[float, float, float]:
    from sklearn.metrics import roc_auc_score

    rng = np.random.default_rng(seed)
    base = roc_auc_score(y, p)
    vals = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() != y[i].max():
            vals.append(roc_auc_score(y[i], p[i]))
    return base, float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def write_metrics_db(rows: list[tuple]) -> bool:
    """rows: (model, metric, value, note). Best-effort: returns False if the database is not reachable."""
    try:
        from .common import pg_connect

        conn = pg_connect()
    except Exception:
        return False
    with conn, conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS gold")
        cur.execute("""CREATE TABLE IF NOT EXISTS gold.ml_metrics (run_at timestamptz DEFAULT now(), model text, metric text, value double precision, note text)""")
        for r in rows:
            cur.execute("INSERT INTO gold.ml_metrics (model, metric, value, note) VALUES (%s,%s,%s,%s)", r)
    conn.close()
    return True
