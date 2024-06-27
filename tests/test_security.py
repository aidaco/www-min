import requests
import urllib.parse

from .utils import run_server, wait_for_healthcheck


def test_authenticate_api():
    with run_server():
        wait_for_healthcheck()
        resp = requests.post(
            url="http://localhost:8000/api/token",
            data={"username": "admin", "password": "password"},
        )
        assert resp.ok
        token = resp.json()["token"]
        assert requests.get(
            "http://localhost:8000/admin.html", headers={"Authorization": token}
        ).ok
        resp = requests.get("http://localhost:8000/admin.html")
        assert resp.ok
        assert urllib.parse.urlparse(resp.url).path == "/login.html"


def test_authenticate_form():
    with run_server():
        wait_for_healthcheck()
        with requests.Session() as session:
            assert session.post(
                url="http://localhost:8000/form/login",
                data={"username": "admin", "password": "password"},
            ).ok
            assert session.get("http://localhost:8000/admin.html").ok
