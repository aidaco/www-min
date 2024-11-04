from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Annotated, NotRequired, Protocol, TypedDict, Unpack
import itertools
import sqlite3

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


class LinkCategoryParams(TypedDict):
    name: str
    created_at: NotRequired[datetime]
    updated_at: NotRequired[datetime]


@dataclass
class LinkCategoryData:
    name: str
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime | None = None


@dataclass
class LinkCategory:
    id: appbase.INTPK
    name: str
    created_at: datetime
    updated_at: datetime | None


class ContactLinkParams(TypedDict):
    name: str
    href: str
    category_id: int
    created_at: NotRequired[datetime]
    updated_at: NotRequired[datetime]


@dataclass
class ContactLinkData:
    name: str
    href: str
    category_id: int
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime | None = None


@dataclass
class ContactLink:
    id: appbase.INTPK
    name: str
    href: str
    category_id: Annotated[
        int, "REFERENCES link_category(id) ON UPDATE CASCADE ON DELETE CASCADE"
    ]
    created_at: datetime
    updated_at: datetime | None


class LinkCategoryStore(appbase.Table[LinkCategory]):
    model = LinkCategory

    def by_id(self, id: int) -> LinkCategory:
        return self.select().where("id=:id").execute(id=id).one()

    def by_name(self, name: str) -> LinkCategory:
        return self.select().where("name=:name").execute(name=name).one()

    def add_category(self, **params: Unpack[LinkCategoryParams]) -> LinkCategory:
        return self.insert().values(LinkCategoryData(**params)).execute().one()


class ContactLinkStore(appbase.Table[ContactLink]):
    model = ContactLink

    def by_category(self, category_id: int) -> list[ContactLink]:
        return (
            self.select()
            .where("category_id=:category_id")
            .execute(category_id=category_id)
            .all()
        )

    def group_by_category(self) -> dict[int, list[ContactLink]]:
        return {
            key: list(group)
            for key, group in itertools.groupby(
                self.select().groupby("category_id").execute().iter(),
                key=lambda row: row.category_id,
            )
        }


def get_contact_links(db: sqlite3.Connection) -> dict[Category, list[Link]]:
    db_links = ContactLinkStore(connection=db).group_by_category()
    categories = LinkCategoryStore(connection=db).select().execute().all()
    result = {
        Category(name=category.name): [
            Link(category.name, link.name, link.href) for link in db_links[category.id]
        ]
        for category in categories
    }
    return result


api = APIRouter()


@api.post("/api/links/categories", status_code=201, response_model=LinkCategory)
async def post_category(
    db: database.depends,
    _: security.authenticated,
    name: Annotated[str, Form()],
):
    category = (
        LinkCategoryStore(connection=db).insert().values(name=name).execute().one()
    )
    return category


@api.post("/form/links/categories")
async def post_category_form(
    db: database.depends,
    _: security.authenticated,
    name: Annotated[str, Form()],
):
    LinkCategoryStore(connection=db).insert().values(name=name).execute().one()
    return RedirectResponse("/admin.html", status_code=302)


@api.post("/api/links", status_code=201, response_model=ContactLink)
async def post_link(
    db: database.depends,
    _: security.authenticated,
    name: Annotated[str, Form()],
    href: Annotated[str, Form()],
    category_id: Annotated[int, Form()],
):
    link = (
        ContactLinkStore(connection=db)
        .insert()
        .values(name=name, href=href, category_id=category_id)
        .execute()
        .one()
    )
    return link


@api.post("/form/links")
async def post_link_create_form(
    db: database.depends,
    _: security.authenticated,
    name: Annotated[str, Form()],
    href: Annotated[str, Form()],
    category_id: Annotated[int, Form()],
):
    ContactLinkStore(connection=db).insert().values(
        name=name, href=href, category_id=category_id
    ).execute()
    return RedirectResponse("/admin.html", status_code=302)


@api.get("/api/links", response_model=list[ContactLink])
async def get_links(db: database.depends):
    return ContactLinkStore(connection=db).select().execute().all()


@api.post("/api/links/update", response_model=ContactLink)
async def update_link(
    _: security.authenticated,
    db: database.depends,
    id: Annotated[int, Form()],
    name: Annotated[str, Form()],
    href: Annotated[str, Form()],
    category_id: Annotated[int, Form()],
):
    return (
        ContactLinkStore(connection=db)
        .update()
        .set(name=name, href=href, category_id=category_id)
        .where(id=id)
        .execute()
        .one()
    )


@api.post("/form/links/update")
async def post_link_update_form(
    _: security.authenticated,
    db: database.depends,
    id: Annotated[int, Form()],
    name: Annotated[str, Form()],
    href: Annotated[str, Form()],
    category_id: Annotated[int, Form()],
):
    ContactLinkStore(connection=db).update().set(
        name=name, href=href, category_id=category_id
    ).where(id=id).execute()
    return RedirectResponse("/admin.html", status_code=302)
