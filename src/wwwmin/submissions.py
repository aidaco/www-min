from typing import Annotated
from fastapi import APIRouter, BackgroundTasks, Form, HTTPException
from fastapi.responses import RedirectResponse

from . import webpush, security, database, operating_hours

api = APIRouter()


@api.post("/api/messages", status_code=201)
async def submit_message(
    db: database.depends,
    tasks: BackgroundTasks,
    email: Annotated[str, Form()],
    message: Annotated[str, Form()],
    phone: Annotated[str | None, Form()] = None,
):
    if not operating_hours.open_now():
        return operating_hours.closed_json()
    submission = db.contact_form_submissions.insert(
        email=email, message=message, phone=phone
    )
    tasks.add_task(
        webpush.notify_all,
        db,
        {
            "title": f"Contact Submission - {submission.email} {submission.phone}",
            "body": f"{submission.message}",
        },
    )
    return RedirectResponse("/", status_code=302)


@api.get("/api/messages")
async def list_messages(_: security.authenticated, db: database.depends):
    return db.contact_form_submissions.iter()


@api.post("/api/messages/archive")
async def archive_message(
    _: security.authenticated, db: database.depends, id: Annotated[int, Form()]
):
    message = db.contact_form_submissions.get(id)
    if not message:
        raise HTTPException(404, "Not Found.")
    message.archive()
    return RedirectResponse("/admin.html", status_code=302)


@api.post("/api/messages/unarchive")
async def unarchive_message(
    _: security.authenticated, db: database.depends, id: Annotated[int, Form()]
):
    message = db.contact_form_submissions.get(id)
    if not message:
        raise HTTPException(404, "Not Found.")
    message.unarchive()
    return RedirectResponse("/admin.html", status_code=302)
