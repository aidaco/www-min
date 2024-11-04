from dataclasses import dataclass, field
from typing import Annotated, Iterator
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Body, Form, HTTPException
from fastapi.responses import RedirectResponse
import appbase

from . import webpush, security, database, operating_hours, emailing


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class ContactFormSubmissionInfo:
    email: str
    message: str
    phone: str | None = None
    received_at: datetime = field(default_factory=utcnow)
    archived_at: datetime | None = None


@dataclass
class ContactFormSubmission:
    id: appbase.INTPK
    email: str
    message: str
    phone: str | None
    received_at: datetime
    archived_at: datetime | None


class ContactFormSubmissionStore(appbase.Table[ContactFormSubmission]):
    model = ContactFormSubmission

    def add_submission(
        self,
        email: str,
        message: str,
        phone: str | None = None,
    ) -> ContactFormSubmission:
        data = ContactFormSubmissionInfo(email=email, message=message, phone=phone)
        return self.insert().values(data).execute().one()

    def archive(self, id: int) -> ContactFormSubmission:
        return self.update().set(archived_at=utcnow()).where(id=id).execute().one()

    def unarchive(self, id: int) -> ContactFormSubmission:
        return self.update().set(archived_at=None).where(id=id).execute().one()

    def archived(self) -> Iterator[ContactFormSubmission]:
        return self.select().where("archived_at IS NOT NULL").execute().iter()

    def active(self) -> Iterator[ContactFormSubmission]:
        return self.select().where("archived_at IS NULL").execute().iter()


api = APIRouter()


@api.post("/api/submissions", status_code=201, response_model=ContactFormSubmission)
async def post_submission(
    db: database.depends,
    _: operating_hours.depends,
    tasks: BackgroundTasks,
    email: Annotated[str, Form()],
    message: Annotated[str, Form()],
    phone: Annotated[str | None, Form()] = None,
):
    submission = (
        ContactFormSubmissionStore(connection=db)
        .insert()
        .values(email=email, message=message, phone=phone)
        .execute()
        .one()
    )
    tasks.add_task(emailing.notify_submission, submission)
    tasks.add_task(webpush.notify_submission, submission)
    return submission


@api.post("/form/submissions")
async def post_submission_form(
    db: database.depends,
    _: operating_hours.depends,
    tasks: BackgroundTasks,
    email: Annotated[str, Form()],
    message: Annotated[str, Form()],
    phone: Annotated[str | None, Form()] = None,
):
    if not operating_hours.open_now():
        return operating_hours.closed_json()
    submission = (
        ContactFormSubmissionStore(connection=db)
        .insert()
        .values(email=email, message=message, phone=phone)
        .execute()
        .one()
    )
    tasks.add_task(emailing.notify_submission, submission)
    tasks.add_task(webpush.notify_submission, submission)
    return RedirectResponse("/", status_code=302)


@api.get("/api/submissions", response_model=list[ContactFormSubmission])
async def get_submissions(_: security.authenticated, db: database.depends):
    return ContactFormSubmissionStore(connection=db).select().execute().iter()


@api.post("/api/submissions/archive", status_code=200)
async def archive_submission(
    _: security.authenticated, db: database.depends, id: Annotated[int, Body()]
):
    submission = ContactFormSubmissionStore(connection=db).archive(id)
    if not submission:
        raise HTTPException(404, "Not Found.")
    return submission


@api.post("/api/submissions/unarchive", status_code=200)
async def post_unarchive_submission(
    _: security.authenticated, db: database.depends, id: Annotated[int, Body()]
):
    submission = ContactFormSubmissionStore(connection=db).unarchive(id)
    if not submission:
        raise HTTPException(404, "Not Found.")
    return submission


@api.post("/form/submissions/archive")
async def post_archive_submission_form(
    _: security.authenticated, db: database.depends, id: Annotated[int, Form()]
):
    submission = ContactFormSubmissionStore(connection=db).archive(id)
    if not submission:
        raise HTTPException(404, "Not Found.")
    return RedirectResponse("/admin.html", status_code=302)


@api.post("/form/submissions/unarchive")
async def post_unarchive_submission_form(
    _: security.authenticated, db: database.depends, id: Annotated[int, Form()]
):
    submission = ContactFormSubmissionStore(connection=db).unarchive(id)
    if not submission:
        raise HTTPException(404, "Not Found.")
    return RedirectResponse("/admin.html", status_code=302)
