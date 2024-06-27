from .utils import run_server, wait_for_response


def test_main_is_importable():
    pass


def test_server_starts():
    with run_server():
        content = wait_for_response("http://localhost:8000/api/health").json()
        assert content == {"status": "ok"}
