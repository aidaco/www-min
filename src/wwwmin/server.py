from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from rich import print

from . import (
    links,
    security,
    github_webhook,
    webpush,
    submissions,
    assets,
    database,
    operating_hours,
    emailing,
)
from .config import configconfig


@configconfig.section("server")
class config:
    host: str = "0.0.0.0"
    port: int = 8000


@asynccontextmanager
async def lifespan(_):
    async with assets.lifespan(_):
        yield


api = FastAPI(lifespan=lifespan)
api.include_router(links.api)
api.include_router(security.api)
api.include_router(submissions.api)
security.install_exception_handler(api)
api.include_router(webpush.api)
if github_webhook.config.enabled:
    api.include_router(github_webhook.api)
api.include_router(assets.api)
if emailing.config.enabled:
    emailing.install_exception_handler(api)
if operating_hours.config.enabled:
    operating_hours.install_exception_handler(api)


@api.get("/api/health")
async def health_check(templates: assets.depends, _: operating_hours.depends):
    try:
        _ = database.connection.execute("select count(*) from user;").fetchone()
        _ = templates.get_template("index.html")
    except Exception as e:
        raise HTTPException(status_code=503, detail="Database error: " + str(e))

    return JSONResponse(content={"status": "ok"})


def serve():
    try:
        uvicorn.run(api, host=config.host, port=config.port)
    except KeyboardInterrupt:
        print("[red]Stopped.[/]")
