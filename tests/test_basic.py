from .utils import run_server, wait_for_healthcheck


def test_main_is_importable():
    pass


def test_server_starts():
    with run_server():
        assert wait_for_healthcheck().json() == {"status": "ok", "site_open": True}


def test_health_reports_database_failure_without_internal_details():
    with run_server(close_database=True):
        response = wait_for_healthcheck()
        assert response.status_code == 503
        assert response.json() == {"detail": "Application is not ready"}
