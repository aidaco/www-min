from dataclasses import dataclass, field

from typing import Annotated, Protocol
from fastapi import APIRouter, Form
from fastapi.responses import RedirectResponse

from . import security, database
from .config import config as main_config


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


@main_config.section("links")
class config:
    links: list[Link] = field(default_factory=list)


def contact_links() -> dict[CategoryType, list[LinkType]]:
    result: dict[CategoryType, list[LinkType]] = (
        database.database.contact_links.group_by_category()  # type: ignore
    )
    for link in config.links:
        result.setdefault(Category(link.category), []).append(link)
    return result


api = APIRouter()


@api.post(
    "/api/links/categories", status_code=201, response_model=database.LinkCategory
)
async def post_category(
    db: database.depends,
    _: security.authenticated,
    name: Annotated[str, Form()],
):
    category = db.link_categories.insert(name=name)
    return category


@api.post("/form/links/categories")
async def post_category_form(
    db: database.depends,
    _: security.authenticated,
    name: Annotated[str, Form()],
):
    db.link_categories.insert(name=name)
    return RedirectResponse("/admin.html", status_code=302)


@api.post("/api/links", status_code=201, response_model=database.ContactLink)
async def post_link(
    db: database.depends,
    _: security.authenticated,
    name: Annotated[str, Form()],
    href: Annotated[str, Form()],
    category_id: Annotated[int, Form()],
):
    link = db.contact_links.insert(name=name, href=href, category_id=category_id)
    return link


@api.post("/form/links")
async def post_link_create_form(
    db: database.depends,
    _: security.authenticated,
    name: Annotated[str, Form()],
    href: Annotated[str, Form()],
    category_id: Annotated[int, Form()],
):
    db.contact_links.insert(name=name, href=href, category_id=category_id)
    return RedirectResponse("/admin.html", status_code=302)


@api.get("/api/links", response_model=list[database.ContactLink])
async def get_links(db: database.depends):
    return db.contact_links.iter()


@api.post("/api/links/update", status_code=200)
async def update_link(
    _: security.authenticated,
    db: database.depends,
    id: Annotated[int, Form()],
    name: Annotated[str, Form()],
    href: Annotated[str, Form()],
    category_id: Annotated[int, Form()],
):
    return db.contact_links.update(id, name, href, category_id)


@api.post("/form/links/update")
async def post_link_update_form(
    _: security.authenticated,
    db: database.depends,
    id: Annotated[int, Form()],
    name: Annotated[str, Form()],
    href: Annotated[str, Form()],
    category_id: Annotated[int, Form()],
):
    db.contact_links.update(id, name, href, category_id)
    return RedirectResponse("/admin.html", status_code=302)
