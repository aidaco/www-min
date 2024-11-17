import time
import multiprocessing
import functools
import unittest.mock
import contextlib
import datetime
import zoneinfo
import os
import signal

import requests


@functools.wraps(requests.get)
def wait_for_response(*args, timeout: int = 10, **kwargs) -> requests.Response:
    start = time.perf_counter()
    while True:
        try:
            return requests.get(*args, **kwargs)
        except requests.ConnectionError as exc:
            if time.perf_counter() - start < timeout:
                time.sleep(0.5)
            else:
                raise exc


def wait_for_healthcheck(
    timeout: int = 10, headers={"accept": "application/json"}, **kwargs
) -> requests.Response:
    resp = wait_for_response(
        "http://localhost:8000/api/health", timeout=timeout, headers=headers, **kwargs
    )
    return resp


BASE_CONFIG = {
    "database": {"uri": ":memory:"},
    "operating_hours": {"enabled": False},
}


@contextlib.contextmanager
def run_server(
    config: dict = BASE_CONFIG,
    frozendt: datetime.datetime = datetime.datetime.now(
        tz=zoneinfo.ZoneInfo("America/New_York")
    ),
    user_credentials: list[tuple[str, str]] = [("admin", "password")],
):
    def _run_target(config, frozendt):
        import wwwmin.config

        wwwmin.config.configconfig.reload(mapping=config)
        import wwwmin.operating_hours

        with unittest.mock.patch("wwwmin.operating_hours.datetime") as mockdt:
            mockdt.now.return_value = frozendt
            import wwwmin.server
            import wwwmin.security

            for username, password in user_credentials:
                wwwmin.security.User.create(username, password)

            wwwmin.server.serve()

    proc = multiprocessing.Process(target=_run_target, args=(config, frozendt))
    proc.start()
    try:
        yield
    finally:
        if proc.pid is not None:
            os.kill(proc.pid, signal.SIGINT)
        else:
            proc.terminate()
        proc.join(10)
        assert proc.exitcode == 0
