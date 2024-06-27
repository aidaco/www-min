from datetime import datetime
import zoneinfo

from .utils import run_server, wait_for_healthcheck

COMMON_CONFIG = {"database": {"uri": ":memory:"}, "operating_hours": {"enabled": True}}
OPEN_DT = datetime(2024, 6, 26, 12, 0, tzinfo=zoneinfo.ZoneInfo("America/New_York"))
CLOSED_DT = datetime(2024, 6, 26, 18, 0, tzinfo=zoneinfo.ZoneInfo("America/New_York"))


def test_operating_hours_open():
    with run_server(config=COMMON_CONFIG, frozendt=OPEN_DT):
        data = wait_for_healthcheck()
        assert data.status_code == 200
        assert data.json() == {"status": "ok"}


def test_operating_hours_closed():
    with run_server(config=COMMON_CONFIG, frozendt=CLOSED_DT):
        data = wait_for_healthcheck().json()
        assert data["status"] == "closed"
