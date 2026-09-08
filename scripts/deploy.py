#!/usr/bin/env python3
"""CI client for Piac's forced SSH command. Secrets travel over stdin, never argv."""

import json
import os
import subprocess
import sys

payload = {"action": sys.argv[1], "image": os.environ["WWWMIN_IMAGE"]}
if payload["action"] == "deploy":
    payload["token"] = os.environ["GH_TOKEN"]
subprocess.run(
    [
        "ssh",
        "-T",
        "-i",
        os.environ["WWWMIN_SSH_KEY_FILE"],
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        "-o",
        "ServerAliveInterval=15",
        "-o",
        "ServerAliveCountMax=4",
        "-o",
        "UserKnownHostsFile=" + os.environ["WWWMIN_KNOWN_HOSTS_FILE"],
        "wwwmin-deploy@77.93.154.112",
    ],
    input=json.dumps(payload),
    text=True,
    check=True,
    timeout=900,
)
