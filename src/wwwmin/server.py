from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from . import security, github_webhook, webpush, submissions, assets, database


@asynccontextmanager
async def lifespan(_):
    async with database.lifespan(_), assets.lifespan(_):
        yield


api = FastAPI(lifespan=lifespan)
api.include_router(security.api)
api.include_router(submissions.api)
security.install_exception_handler(api)
api.include_router(webpush.api)
api.include_router(github_webhook.api)
api.include_router(assets.api)


@api.get("/api/health")
async def health_check(db: database.depends, templates: assets.depends):
    try:
        _ = db.query("SELECT 1").fetchone()  # Simple query to test connection
        _ = templates.get_template("index.html")
    except Exception as e:
        raise HTTPException(status_code=503, detail="Database error: " + str(e))

    return JSONResponse(content={"status": "ok"})


def serve():
    uvicorn.run(api)
