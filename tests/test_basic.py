import subprocess
import signal
import time

import requests


def test_import_toplevel():
    pass


def test_server_starts():
    proc = subprocess.Popen(
        ["wwwmin-serve"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(5)
    with requests.Session() as session:
        content = session.get("http://localhost:8000/api/health").json()
        assert content == {"status": "ok"}
    proc.send_signal(signal.SIGINT)
    proc.wait()
    assert proc.returncode == 0
