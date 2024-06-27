from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from rich import print

from . import (
    security,
    github_webhook,
    webpush,
    submissions,
    assets,
    database,
    operating_hours,
    emailing,
)
from .config import config as main_config


@main_config.section("server")
class config:
    host: str = "localhost"
    port: int = 8000


@asynccontextmanager
async def lifespan(_):
    async with assets.lifespan(_):
        yield


api = FastAPI(lifespan=lifespan)
api.include_router(security.api)
api.include_router(submissions.api)
security.install_exception_handler(api)
api.include_router(webpush.api)
if github_webhook.config.enabled:
    api.include_router(github_webhook.api)
api.include_router(assets.api)
if emailing.config.enabled:
    emailing.install_exception_handler(api)


@api.get("/api/health")
async def health_check(db: database.depends, templates: assets.depends):
    if not operating_hours.open_now():
        return operating_hours.closed_json()
    try:
        _ = db.query("SELECT 1").fetchone()  # Simple query to test connection
        _ = templates.get_template("index.html")
    except Exception as e:
        raise HTTPException(status_code=503, detail="Database error: " + str(e))

    return JSONResponse(content={"status": "ok"})


def serve():
    try:
        uvicorn.run(api, host=config.host, port=config.port)
    except KeyboardInterrupt:
        print("[red]Stopped.[/]")
