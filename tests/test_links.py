import requests
from .utils import run_server, wait_for_healthcheck, BASE_CONFIG


def test_config():
    test_value = "mailto:contact@aidan.software"
    with run_server(
        config=BASE_CONFIG
        | {
            "links": {
                "links": [{"category": "contact", "name": "email", "href": test_value}]
            }
        }
    ):
        wait_for_healthcheck()
        data = requests.get("http://localhost:8000/").text
        print(data)
        assert test_value in data


def test_api():
    with run_server():
        wait_for_healthcheck()
        test_value = "TEST VALUE as;dfjoa8weu"
        assert test_value not in requests.get("http://localhost:8000/").text
        token = requests.post(
            "http://localhost:8000/api/token",
            {"username": "admin", "password": "password"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        ).json()["token"]
        cat = requests.post(
            "http://localhost:8000/api/links/categories",
            {"name": "personal"},
            headers={"Authorization": token},
        ).json()
        requests.post(
            "http://localhost:8000/api/links",
            {
                "name": "contact",
                "href": test_value,
                "category_id": cat["id"],
            },
            headers={"Authorization": token},
        ).json()
        assert test_value in requests.get("http://localhost:8000/").text
