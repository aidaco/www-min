from typing import Annotated
from fastapi import APIRouter, BackgroundTasks, Body, Form, HTTPException
from fastapi.responses import RedirectResponse

from . import webpush, security, database, operating_hours, emailing

api = APIRouter()


@api.post(
    "/api/submissions", status_code=201, response_model=database.ContactFormSubmission
)
async def post_submission(
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
    tasks.add_task(emailing.notify_submission, submission)
    tasks.add_task(webpush.notify_submission, submission)
    return submission


@api.post("/form/submissions")
async def post_submission_form(
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
    tasks.add_task(emailing.notify_submission, submission)
    tasks.add_task(webpush.notify_submission, submission)
    return RedirectResponse("/", status_code=302)


@api.get("/api/submissions", response_model=list[database.ContactFormSubmission])
async def get_submissions(_: security.authenticated, db: database.depends):
    return db.contact_form_submissions.iter()


@api.post("/api/submissions/archive", status_code=200)
async def archive_submission(
    _: security.authenticated, db: database.depends, id: Annotated[int, Body()]
):
    submission = db.contact_form_submissions.get(id)
    if not submission:
        raise HTTPException(404, "Not Found.")
    submission.archive()


@api.post("/api/submissions/unarchive", status_code=200)
async def post_unarchive_submission(
    _: security.authenticated, db: database.depends, id: Annotated[int, Body()]
):
    submission = db.contact_form_submissions.get(id)
    if not submission:
        raise HTTPException(404, "Not Found.")
    submission.unarchive()


@api.post("/form/submissions/archive")
async def post_archive_submission_form(
    _: security.authenticated, db: database.depends, id: Annotated[int, Form()]
):
    submission = db.contact_form_submissions.get(id)
    if not submission:
        raise HTTPException(404, "Not Found.")
    submission.archive()
    return RedirectResponse("/admin.html", status_code=302)


@api.post("/form/submissions/unarchive")
async def post_unarchive_submission_form(
    _: security.authenticated, db: database.depends, id: Annotated[int, Form()]
):
    submission = db.contact_form_submissions.get(id)
    if not submission:
        raise HTTPException(404, "Not Found.")
    submission.unarchive()
    return RedirectResponse("/admin.html", status_code=302)
