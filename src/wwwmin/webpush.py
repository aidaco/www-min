from typing import Annotated, Any
import json

from fastapi import APIRouter, Body
from fastapi.responses import PlainTextResponse
import py_vapid
from pywebpush import webpush, WebPushException

from . import security, database


VAPID_PRIVATE_KEY_FILE = "vapid-private-key.pem"
vapid = py_vapid.Vapid.from_file(VAPID_PRIVATE_KEY_FILE)
api = APIRouter()


def notify_all(db: database.WWWMINDatabase, data: dict) -> None:
    payload = json.dumps(data)
    for subscription in db.web_push_subscription.iter():
        try:
            webpush(
                json.loads(subscription.subscription),
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY_FILE,
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
    db.web_push_subscription.insert(user_id=user.id, subscription=subscription)
