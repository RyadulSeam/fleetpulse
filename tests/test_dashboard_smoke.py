from pathlib import Path

import pytest

pytest.importorskip("streamlit")


@pytest.mark.integration
def test_dashboard_renders_without_exceptions():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "services" / "dashboard" / "app.py"), default_timeout=60).run()
    assert not at.exception, [e.value for e in at.exception]
