from dataclasses import dataclass
from typing import Annotated, ClassVar, Iterator, Self, Callable, Awaitable
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Body, Form, HTTPException
from fastapi.responses import RedirectResponse
import appbase

from . import security, database, operating_hours
from .util import utcnow


@dataclass
class ContactFormSubmission:
    id: appbase.database.INTPK
    email: str
    message: str
    phone: str | None
    received_at: datetime
    archived_at: datetime | None

    subscribers: ClassVar[set[Callable[[Self], Awaitable[None]]]] = set()

    @classmethod
    def subscribe(
        cls, corofn: Callable[[Self], Awaitable[None]]
    ) -> Callable[[Self], Awaitable[None]]:
        cls.subscribers.add(corofn)
        return corofn

    @classmethod
    def unsubscribe(cls, corofn: Callable[[Self], Awaitable[None]]) -> None:
        cls.subscribers.discard(corofn)

    def notify_in_backgroundtasks(self, tasks: BackgroundTasks) -> None:
        for corofn in self.subscribers:
            tasks.add_task(corofn, self)

    @classmethod
    def create(
        cls,
        email: str,
        message: str,
        phone: str | None = None,
        received_at: datetime | None = None,
        archived_at: datetime | None = None,
    ) -> Self | None:
        return (
            database.connection.table(cls)
            .insert()
            .values(
                email=email,
                message=message,
                phone=phone,
                received_at=received_at or utcnow(),
                archived_at=archived_at,
            )
            .returning("*")
            .execute()
            .one()
        )

    @classmethod
    def get_by_id(cls, id: int) -> Self | None:
        return database.connection.table(cls).select().where(id=id).execute().one()

    @classmethod
    def archive(cls, id: int) -> Self | None:
        return (
            database.connection.table(cls)
            .update()
            .set(archived_at=utcnow())
            .where(id=id)
            .returning("*")
            .execute()
            .one()
        )

    @classmethod
    def unarchive(cls, id: int) -> Self | None:
        return (
            database.connection.table(cls)
            .update()
            .set(archived_at=None)
            .where(id=id)
            .execute()
            .one()
        )

    @classmethod
    def archived(cls) -> Iterator[Self]:
        return (
            database.connection.table(cls)
            .select()
            .where("archived_at IS NOT NULL")
            .execute()
            .iter()
        )

    @classmethod
    def active(cls) -> Iterator[Self]:
        return (
            database.connection.table(cls)
            .select()
            .where("archived_at IS NULL")
            .execute()
            .iter()
        )

    @classmethod
    def iterall(cls) -> Iterator[Self]:
        yield from database.connection.table(cls).select().execute().iter()


api = APIRouter()


@api.post("/api/submissions", status_code=201, response_model=ContactFormSubmission)
async def post_submission(
    _: operating_hours.depends,
    tasks: BackgroundTasks,
    email: Annotated[str, Form()],
    message: Annotated[str, Form()],
    phone: Annotated[str | None, Form()] = None,
):
    submission = ContactFormSubmission.create(email=email, message=message, phone=phone)
    if submission is None:
        raise HTTPException(status_code=500, detail="Failed to create submission.")
    submission.notify_in_backgroundtasks(tasks)
    return submission


@api.post("/form/submissions")
async def post_submission_form(
    _: operating_hours.depends,
    tasks: BackgroundTasks,
    email: Annotated[str, Form()],
    message: Annotated[str, Form()],
    phone: Annotated[str | None, Form()] = None,
):
    submission = ContactFormSubmission.create(email=email, message=message, phone=phone)
    if submission is None:
        raise HTTPException(status_code=500, detail="Failed to create submission.")
    submission.notify_in_backgroundtasks(tasks)
    return RedirectResponse("/", status_code=302)


@api.get("/api/submissions", response_model=list[ContactFormSubmission])
async def get_submissions(_: security.authenticated):
    return list(ContactFormSubmission.iterall())


@api.post("/api/submissions/archive", status_code=200)
async def archive_submission(_: security.authenticated, id: Annotated[int, Body()]):
    submission = ContactFormSubmission.archive(id)
    if not submission:
        raise HTTPException(404, "Submission not Found.")
    return submission


@api.post("/api/submissions/unarchive", status_code=200)
async def post_unarchive_submission(
    _: security.authenticated, id: Annotated[int, Body()]
):
    submission = ContactFormSubmission.unarchive(id)
    if not submission:
        raise HTTPException(404, "Not Found.")
    return submission


@api.post("/form/submissions/archive")
async def post_archive_submission_form(
    _: security.authenticated, id: Annotated[int, Form()]
):
    submission = ContactFormSubmission.archive(id)
    if not submission:
        raise HTTPException(404, "Not Found.")
    return RedirectResponse("/admin.html", status_code=302)


@api.post("/form/submissions/unarchive")
async def post_unarchive_submission_form(
    _: security.authenticated, id: Annotated[int, Form()]
):
    submission = ContactFormSubmission.unarchive(id)
    if not submission:
        raise HTTPException(404, "Not Found.")
    return RedirectResponse("/admin.html", status_code=302)


database.connection.table(ContactFormSubmission).create().if_not_exists().execute()
