import pytest

pytest.importorskip("httpx2")
pytest.importorskip("joblib")
from pathlib import Path  # noqa: E402

if not (Path(__file__).resolve().parents[1] / "models" / "delay_model.joblib").exists():
    pytest.skip("train models first (step 08)", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from services.api.main import app  # noqa: E402

c = TestClient(app)


def test_health():
    assert c.get("/health").json()["status"] == "ok"


def test_prediction_always_carries_reliability_status():
    r = c.post("/predict", json={"hub_id": 1}).json()
    assert 0 <= r["delay_probability"] <= 1 and "model_status" in r and "evidence" in r


def test_validation_rejects_bad_hub():
    assert c.post("/predict", json={"hub_id": 99}).status_code == 422
