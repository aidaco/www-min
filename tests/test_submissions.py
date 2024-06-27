import requests
from .utils import run_server, wait_for_healthcheck


def test_api():
    with run_server():
        wait_for_healthcheck()
        data = {
            "email": "test@example.com",
            "phone": "1234567890",
            "message": "test message abc",
        }
        submission = requests.post("http://localhost:8000/api/submissions", data).json()
        assert submission["id"] == 1
        assert submission["message"] == "test message abc"
