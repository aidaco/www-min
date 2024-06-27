import asyncio
import hashlib
import hmac
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import psutil
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from .config import config as main_config


api = APIRouter()


@main_config.section("cd")
class config:
    enabled: bool = True
    vcs_package_url: str = "git+https://github.com/aidaco/www-min"
    vcs_wd: Path = Path.cwd()
    branch: str = "main"
    secret: str = "secret value"
    check: bool = True


async def cleanup():
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [t.cancel() for t in tasks]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass

    pid = os.getpid()
    parent = psutil.Process(pid)
    for ch in parent.children(recursive=True):
        for fd in ch.open_files() + ch.connections():
            try:
                os.fsync(fd.fd)
                os.close(fd.fd)
            except OSError:
                pass


async def upgrade_and_restart(vcs_url: str):
    await cleanup()
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", vcs_url],
        check=True,
        cwd=config.vcs_wd,
    )
    os.execv(sys.orig_argv[0], sys.orig_argv)


def verify_signature(body: bytes, signature: str, secret: str) -> None:
    if not signature:
        raise HTTPException(status_code=403, detail="Missing payload signature.")
    hasher = hmac.new(
        secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    )
    if not hmac.compare_digest(f"sha256={hasher.hexdigest()}", signature):
        raise HTTPException(status_code=403, detail="Failed to verify signature.")


def check_branch(body: bytes, branch: str) -> bool:
    try:
        data = json.loads(body.decode("utf-8"))
        requested = data["ref"]
    except (json.JSONDecodeError, KeyError):
        return False
    return requested == f"refs/heads/{branch}"


@api.post("/api/webhook/{appname}", status_code=200)
async def receive_webhook(
    request: Request,
    appname: str,
    x_github_event: Annotated[str, Header()],
    x_hub_signature_256: Annotated[str, Header()],
    tasks: BackgroundTasks,
):
    match x_github_event:
        case "ping":
            return {"message": "pong"}
        case "push":
            pass
        case _:
            return
    body = await request.body()
    if config.check:
        if not check_branch(body, config.branch):
            return
        verify_signature(body, x_hub_signature_256, config.secret)
    tasks.add_task(upgrade_and_restart, config.vcs_package_url)
