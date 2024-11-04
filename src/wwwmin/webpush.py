from dataclasses import dataclass, field
from typing import Annotated, Any, NotRequired, TypedDict, Unpack
from pathlib import Path
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Body
from fastapi.responses import PlainTextResponse
import py_vapid
from pywebpush import webpush, WebPushException
import appbase

from . import security, database
from .submissions import ContactFormSubmission
from .config import configconfig


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@configconfig.section("webpush")
class config:
    vapid_private_key_file: Path = configconfig.source.datadir / "vapid-private-key.pem"


config.vapid_private_key_file.parent.mkdir(parents=True, exist_ok=True)
vapid = py_vapid.Vapid.from_file(config.vapid_private_key_file)


class WebPushSubscriptionParams(TypedDict):
    user_id: int
    subscription: str
    subscribed_at: NotRequired[datetime]


@dataclass
class WebPushSubscriptionData:
    user_id: int
    subscription: str
    subscribed_at: datetime = field(default_factory=utcnow)


@dataclass
class WebPushSubscription:
    id: appbase.INTPK
    user_id: Annotated[int, "REFERENCES user(id) ON UPDATE CASCADE ON DELETE CASCADE"]
    subscription: str
    subscribed_at: datetime


class WebPushSubscriptionStore(appbase.Table[WebPushSubscription]):
    model = WebPushSubscription

    def subscribe_user(
        self, **params: Unpack[WebPushSubscriptionParams]
    ) -> WebPushSubscription:
        data = WebPushSubscriptionData(**params)
        return self.insert().values(data).execute().one()

    def by_user_id(self, user_id: int) -> list[WebPushSubscription]:
        return self.select().where(user_id=user_id).execute().all()


api = APIRouter()


async def notify_submission(
    store: WebPushSubscriptionStore, submission: ContactFormSubmission
) -> None:
    await notify_all(
        store,
        {
            "title": f"Submission - {submission.email} {submission.phone}",
            "body": f"{submission.message}",
        },
    )


async def notify_all(store: WebPushSubscriptionStore, data: dict) -> None:
    payload = json.dumps(data)
    for subscription in store.select().execute().iter():
        try:
            webpush(
                json.loads(subscription.subscription),
                data=payload,
                vapid_private_key=str(config.vapid_private_key_file.resolve()),
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
    assert vapid.public_key is not None
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
    return (
        WebPushSubscriptionStore(connection=db)
        .insert()
        .values(user_id=user.id, subscription=subscription)
        .execute()
        .one()
    )
