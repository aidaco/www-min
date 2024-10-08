from typing import Annotated, Any
from pathlib import Path
import json

from fastapi import APIRouter, Body
from fastapi.responses import PlainTextResponse
import py_vapid
from pywebpush import webpush, WebPushException

from . import security, database
from .config import config as main_config


@main_config.section("webpush")
class config:
    vapid_private_key_file: Path = main_config.datadir / "vapid-private-key.pem"


config.vapid_private_key_file.parent.mkdir(parents=True, exist_ok=True)
vapid = py_vapid.Vapid.from_file(config.vapid_private_key_file)
api = APIRouter()


async def notify_submission(submission: database.ContactFormSubmission) -> None:
    await notify_all(
        {
            "title": f"Submission - {submission.email} {submission.phone}",
            "body": f"{submission.message}",
        }
    )


async def notify_all(data: dict) -> None:
    payload = json.dumps(data)
    for subscription in database.database.web_push_subscriptions.iter():
        try:
            webpush(
                json.loads(subscription.subscription),
                data=payload,
                vapid_private_key=config.vapid_private_key_file,
                vapid_claims={
                    "sub": "mailto:push@aidan.software",
                },
            )
        except WebPushException as ex:
            if ex.response and ex.response.json():
                extra = ex.response.json()
                print(
                    "Remote service replied with a {}:{}, {}",
                    extra.code,
                    extra.errno,
                    extra.message,
                )


@api.get("/api/vapid-public-key", response_class=PlainTextResponse)
async def get_vapid_public_key():
    return py_vapid.b64urlencode(
        vapid.public_key.public_bytes(
            py_vapid.serialization.Encoding.X962,
            py_vapid.serialization.PublicFormat.UncompressedPoint,
        )
    )


@api.post("/api/register-push-subscription")
async def register_web_push_subscription(
    db: database.depends,
    user: security.authenticated,
    subscription: Annotated[Any, Body()],
):
    db.web_push_subscriptions.insert(user_id=user.id, subscription=subscription)
