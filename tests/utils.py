import time
import multiprocessing
import functools
import unittest.mock
import contextlib
import datetime
import zoneinfo
import os
import signal
import subprocess

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


@contextlib.contextmanager
def run_server_cli():
    proc = subprocess.Popen(
        ["wwwmin-serve"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        yield
    finally:
        proc.send_signal(signal.SIGINT)
        proc.wait()
        assert proc.returncode == 0


@contextlib.contextmanager
def run_server(
    config: dict = {"database": {"uri": ":memory:"}},
    frozendt: datetime.datetime = datetime.datetime.now(
        tz=zoneinfo.ZoneInfo("America/New_York")
    ),
):
    def _run_target(config, frozendt):
        import wwwmin.config

        wwwmin.config.config._data = config
        import wwwmin.operating_hours

        with unittest.mock.patch("wwwmin.operating_hours.datetime") as mockdt:
            mockdt.now.return_value = frozendt
            import wwwmin.__main__

            wwwmin.__main__.main()

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
