from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Annotated, Any, Iterator, Protocol, Self
import itertools
import pydantic

from fastapi import APIRouter, Form
from fastapi.responses import RedirectResponse
import appbase

from . import security, database
from .config import configconfig


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class CategoryType(Protocol):
    @property
    def name(self) -> str: ...


class LinkType(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def href(self) -> str: ...


@dataclass(frozen=True)
class Category:
    name: str


@dataclass(frozen=True)
class Link:
    category: str
    name: str
    href: str


@configconfig.section("links")
class config:
    links: list[Link] = field(default_factory=list)


class LinkCategoryData(pydantic.BaseModel):
    name: str
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime | None = None


@dataclass
class LinkCategory:
    id: appbase.database.INTPK
    name: str
    created_at: datetime
    updated_at: datetime | None

    @classmethod
    def get_by_id(cls, id: int) -> Self | None:
        return database.connection.table(cls).select().where(id=id).execute().one()

    @classmethod
    def get_by_name(cls, name: str) -> Self | None:
        return database.connection.table(cls).select().where(name=name).execute().one()

    @classmethod
    def create(cls, **kwargs: Any) -> Self | None:
        return (
            database.connection.table(cls)
            .insert()
            .values(LinkCategoryData(**kwargs))
            .execute()
            .one()
        )

    @classmethod
    def group_by_id(cls) -> dict[int, Self]:
        return {
            link.id: link
            for link in database.connection.table(cls).select().execute().iter()
        }


class ContactLinkData(pydantic.BaseModel):
    name: str
    href: str
    category_id: int
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime | None = None


@dataclass
class ContactLink:
    id: appbase.database.INTPK
    name: str
    href: str
    category_id: Annotated[
        int, "REFERENCES link_category(id) ON UPDATE CASCADE ON DELETE CASCADE"
    ]
    created_at: datetime
    updated_at: datetime | None

    @classmethod
    def create(cls, **kwargs: Any) -> Self | None:
        return (
            database.connection.table(cls)
            .insert()
            .values(ContactLinkData(**kwargs))
            .execute()
            .one()
        )

    @classmethod
    def iter_all(cls) -> Iterator[Self]:
        yield from database.connection.table(cls).select().execute().iter()

    @classmethod
    def get_by_category(cls, category_id: int) -> Iterator[Self]:
        yield from (
            database.connection.table(cls)
            .select()
            .where(category_id=category_id)
            .execute()
            .iter()
        )

    @classmethod
    def group_by_category(cls) -> dict[int, list[Self]]:
        table = database.connection.table(cls)
        return {
            key: list(group)
            for key, group in itertools.groupby(
                table.select().groupby("category_id").execute().iter(),
                key=lambda row: row.category_id,
            )
        }


def get_contact_links() -> dict[Category, list[Link]]:
    db_links = ContactLink.group_by_category()
    db_categories = LinkCategory.group_by_id()
    result = {}
    for category_id, links in db_links.items():
        category = db_categories[category_id]
        result[Category(name=category.name)] = [
            Link(category.name, link.name, link.href) for link in links
        ]
    for link in config.links:
        result.setdefault(Category(name=link.category), []).append(link)
    return result


api = APIRouter()


@api.post("/api/links/categories", status_code=201, response_model=LinkCategory)
async def post_category(
    _: security.authenticated,
    name: Annotated[str, Form()],
):
    category = LinkCategory.create(name=name)
    return category


@api.post("/form/links/categories")
async def post_category_form(
    _: security.authenticated,
    name: Annotated[str, Form()],
):
    LinkCategory.create(name=name)
    return RedirectResponse("/admin.html", status_code=302)


@api.post("/api/links", status_code=201, response_model=ContactLink)
async def post_link(
    _: security.authenticated,
    name: Annotated[str, Form()],
    href: Annotated[str, Form()],
    category_id: Annotated[int, Form()],
):
    return ContactLink.create(name=name, href=href, category_id=category_id)


@api.post("/form/links")
async def post_link_create_form(
    _: security.authenticated,
    name: Annotated[str, Form()],
    href: Annotated[str, Form()],
    category_id: Annotated[int, Form()],
):
    database.connection.table(ContactLink).insert().values(
        name=name, href=href, category_id=category_id
    ).execute()
    return RedirectResponse("/admin.html", status_code=302)


@api.get("/api/links", response_model=list[ContactLink])
async def get_links():
    return list(ContactLink.iter_all())


@api.post("/api/links/update", response_model=ContactLink)
async def update_link(
    _: security.authenticated,
    id: Annotated[int, Form()],
    name: Annotated[str, Form()],
    href: Annotated[str, Form()],
    category_id: Annotated[int, Form()],
):
    return (
        database.connection.table(ContactLink)
        .update()
        .set(name=name, href=href, category_id=category_id)
        .where(id=id)
        .execute()
        .one()
    )


@api.post("/form/links/update")
async def post_link_update_form(
    _: security.authenticated,
    id: Annotated[int, Form()],
    name: Annotated[str, Form()],
    href: Annotated[str, Form()],
    category_id: Annotated[int, Form()],
):
    database.connection.table(ContactLink).update().set(
        name=name, href=href, category_id=category_id
    ).where(id=id).execute()
    return RedirectResponse("/admin.html", status_code=302)
