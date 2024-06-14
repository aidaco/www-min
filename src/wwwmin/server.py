from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI

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


def serve():
    uvicorn.run(api)
