from .utils import run_server, wait_for_healthcheck


def test_main_is_importable():
    pass


def test_server_starts():
    with run_server():
        assert wait_for_healthcheck().json() == {"status": "ok"}
