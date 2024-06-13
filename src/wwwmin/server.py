from typing import Annotated, Any
from urllib.parse import quote
import importlib.resources
import json

import uvicorn
from fastapi import (
    Depends,
    FastAPI,
    Form,
    HTTPException,
    Request,
    Query,
    Body,
    BackgroundTasks,
)
from fastapi.responses import PlainTextResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import py_vapid
from pywebpush import webpush, WebPushException

from wwwmin.database import User, ContactFormSubmission, WebPushSubcription
from . import security, github_webhook
import wwwmin.static
import wwwmin.templates


templates: Jinja2Templates
VAPID_PRIVATE_KEY = "vapid-private-key.pem"
vapid = py_vapid.Vapid.from_file(VAPID_PRIVATE_KEY)
api = FastAPI()


async def send_notification(submission: ContactFormSubmission):
    payload = json.dumps(
        {
            "title": f"Contact Submission - {submission.email} {submission.phone}",
            "body": f"{submission.message}",
        }
    )
    for subscription in WebPushSubcription.iter():
        try:
            webpush(
                json.loads(subscription.subscription),
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
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


@api.exception_handler(security.LoginRequired)
def handle_login_required(request: Request, _: security.LoginRequired):
    return RedirectResponse(f"/login.html?next={quote(request.url._url)}")


@api.post("/api/token")
async def submit_login(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "/admin.html",
):
    try:
        user, token = security.login_user(username, password)
    except security.AuthenticationError:
        return RedirectResponse(f"/login.html?next={next!r}", status_code=302)
    response = RedirectResponse("/admin.html", status_code=302)
    response.set_cookie(
        key="Authorization",
        value=token,
        secure=True,
        httponly=True,
        samesite="strict",
        max_age=round(security.JWT_TTL.total_seconds()),
    )
    return response


@api.post("/api/messages", status_code=201)
async def submit_message(
    tasks: BackgroundTasks,
    email: Annotated[str, Form()],
    message: Annotated[str, Form()],
    phone: Annotated[str | None, Form()] = None,
):
    submission = ContactFormSubmission.insert(email=email, message=message, phone=phone)
    tasks.add_task(send_notification, submission)
    return RedirectResponse("/", status_code=302)


@api.get("/api/messages")
async def list_messages(_: Annotated[User, Depends(security.authenticate)]):
    return ContactFormSubmission.iter()


@api.post("/api/messages/archive")
async def archive_message(
    _: Annotated[User, Depends(security.authenticate)], id: Annotated[int, Form()]
):
    message = ContactFormSubmission.get(id)
    if not message:
        raise HTTPException(404, "Not Found.")
    message.archive()
    return RedirectResponse("/admin.html", status_code=302)


@api.post("/api/messages/unarchive")
async def unarchive_message(
    _: Annotated[User, Depends(security.authenticate)], id: Annotated[int, Form()]
):
    message = ContactFormSubmission.get(id)
    if not message:
        raise HTTPException(404, "Not Found.")
    message.unarchive()
    return RedirectResponse("/admin.html", status_code=302)


@api.get("/api/vapid-public-key", response_class=PlainTextResponse)
async def get_vapid_public_key():
    enc = py_vapid.b64urlencode(
        key := vapid.public_key.public_bytes(
            py_vapid.serialization.Encoding.X962,
            py_vapid.serialization.PublicFormat.UncompressedPoint,
        )
    )
    print(key)
    print(enc)
    return enc


@api.post("/api/register-push-subscription")
async def register_web_push_subscription(
    user: Annotated[User, Depends(security.authenticate)],
    subscription: Annotated[Any, Body()],
):
    print(user, subscription)
    WebPushSubcription.insert(user_id=user.id, subscription=subscription)


api.include_router(github_webhook.api)


@api.get("/", response_class=HTMLResponse)
def get_bare_index(request: Request):
    return get_index(request)


@api.get("/index.html", response_class=HTMLResponse)
def get_index(request: Request):
    return templates.TemplateResponse(request, "index.html", context={})


@api.get("/login.html", response_class=HTMLResponse)
def get_login(request: Request, next: Annotated[str, Query()] = ""):
    return templates.TemplateResponse(
        request, "login.html", context={"next_url": quote(next)}
    )


@api.get("/admin.html", response_class=HTMLResponse)
async def get_admin(
    request: Request, _: Annotated[User, Depends(security.authenticate)]
):
    return templates.TemplateResponse(
        request,
        "admin.html",
        context={
            "active_submissions": ContactFormSubmission.active(),
            "archived_submissions": ContactFormSubmission.archived(),
        },
    )


def serve():
    global templates
    static_files = importlib.resources.files(wwwmin.static)
    templates_files = importlib.resources.files(wwwmin.templates)
    with (
        importlib.resources.as_file(static_files) as static,
        importlib.resources.as_file(templates_files) as templates_dir,
    ):
        templates = Jinja2Templates(directory=templates_dir)
        api.mount("/", StaticFiles(directory=static), name="static")
        uvicorn.run(api)
