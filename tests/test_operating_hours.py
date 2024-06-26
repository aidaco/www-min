from datetime import datetime
import zoneinfo

from .utils import run_server, wait_for_response


def test_operating_hours_open():
    with run_server(
        frozendt=datetime(
            2024, 6, 26, 12, 0, tzinfo=zoneinfo.ZoneInfo("America/New_York")
        )
    ):
        data = wait_for_response(
            "http://localhost:8000/api/health", headers={"Accept": "application/json"}
        )
        assert data.status_code == 200
        assert data.json() == {"status": "ok"}


def test_operating_hours_closed():
    with run_server(
        frozendt=datetime(
            2024, 6, 26, 18, 0, tzinfo=zoneinfo.ZoneInfo("America/New_York")
        )
    ):
        data = wait_for_response(
            "http://localhost:8000/api/health", headers={"Accept": "application/json"}
        )
        assert data.status_code == 503
        assert "closed" in data.json()["detail"]
