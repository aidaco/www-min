#!/usr/bin/env python3
"""Read-only production checks. Never submit forms or modify server state."""

import json
import sys
from urllib.error import HTTPError
from urllib.request import urlopen

base = sys.argv[1].rstrip("/")


def get(path):
    try:
        response = urlopen(base + path, timeout=15)
    except HTTPError as exc:
        response = exc
    with response:
        return response.status, response.read()


status, body = get("/api/health")
assert status == 200, f"Health returned {status}"
health = json.loads(body)
assert health["status"] == "ok" and isinstance(health["site_open"], bool)
status, body = get("/")
# Hours can change between requests. Both normal homepage variants are valid.
assert status in (200, 503), f"Homepage returned {status}"
assert b"<html" in body.lower()
if status == 503:
    assert b"This Website is Closed" in body, "Unexpected homepage failure"
for path in ("/styles.css", "/index.js", "/login.html"):
    status, body = get(path)
    assert status == 200 and body, f"{path} returned {status} or an empty body"
print("Read-only website smoke checks passed")
