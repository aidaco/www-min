from dataclasses import dataclass
from typing import Annotated, Any, Iterator, Self
from pathlib import Path
import json
from datetime import datetime

from fastapi import APIRouter, Body
from fastapi.responses import PlainTextResponse
import py_vapid
from pywebpush import webpush, WebPushException
import appbase

from . import security, database
from .submissions import ContactFormSubmission
from .config import configconfig, config as main_config
from .util import utcnow
from wwwmin import submissions


@configconfig.section("webpush")
class config:
    enabled: bool = False
    vapid_private_key_file: Path = main_config().datadir / "vapid-private-key.pem"


@dataclass
class WebPushSubscription:
    id: appbase.database.INTPK
    user_id: Annotated[int, "REFERENCES user(id) ON UPDATE CASCADE ON DELETE CASCADE"]
    subscription: str
    subscribed_at: datetime

    @classmethod
    def subscribe_user(
        cls, user_id: int, subscription: str, subscribed_at: datetime | None = None
    ) -> Self | None:
        return (
            database.connection.table(cls)
            .insert()
            .values(
                user_id=user_id,
                subscription=subscription,
                subscribed_at=subscribed_at or utcnow(),
            )
            .returning("*")
            .execute()
            .one()
        )

    @classmethod
    def get_by_user_id(cls, user_id: int) -> Iterator[Self]:
        yield from (
            database.connection.table(cls)
            .select()
            .where(user_id=user_id)
            .execute()
            .iter()
        )

    @classmethod
    def iterall(cls) -> Iterator[Self]:
        yield from (database.connection.table(cls).select().execute().iter())


api = APIRouter()


async def notify_submission(submission: ContactFormSubmission) -> None:
    await notify_all(
        {
            "title": f"Submission - {submission.email} {submission.phone}",
            "body": f"{submission.message}",
        },
    )


async def notify_all(data: dict) -> None:
    payload = json.dumps(data)
    vapid_pk = str(config().vapid_private_key_file.resolve())
    for subscription in WebPushSubscription.iterall():
        try:
            webpush(
                json.loads(subscription.subscription),
                data=payload,
                vapid_private_key=vapid_pk,
                vapid_claims={"sub": "mailto:push@aidan.software"},
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
    assert vapid.public_key is not None
    return py_vapid.b64urlencode(
        vapid.public_key.public_bytes(
            py_vapid.serialization.Encoding.X962,
            py_vapid.serialization.PublicFormat.UncompressedPoint,
        )
    )


@api.post("/api/register-push-subscription", response_model=WebPushSubscription | None)
async def register_web_push_subscription(
    user: security.authenticated,
    subscription: Annotated[Any, Body()],
):
    return WebPushSubscription.subscribe_user(user.id, subscription)


if config().enabled:
    database.connection.table(WebPushSubscription).create().if_not_exists().execute()
    config().vapid_private_key_file.parent.mkdir(parents=True, exist_ok=True)
    vapid = py_vapid.Vapid.from_file(config().vapid_private_key_file)
    submissions.ContactFormSubmission.subscribe(notify_submission)
