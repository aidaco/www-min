from contextlib import asynccontextmanager
from typing import Annotated
from importlib.resources import files, as_file
from urllib.parse import quote

from fastapi import APIRouter, Request, Depends, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from . import security, static, templates, database, operating_hours, links


@asynccontextmanager
async def lifespan(app):
    static_files = files(static)
    templates_files = files(templates)

    with (
        as_file(static_files) as static_path,
        as_file(templates_files) as templates_path,
    ):
        app.state.templates = Jinja2Templates(directory=templates_path)
        app.mount("/", StaticFiles(directory=static_path), name="static")
        yield


async def _depends_on_templates(request: Request):
    return request.app.state.templates


depends = Annotated[Jinja2Templates, Depends(_depends_on_templates)]


api = APIRouter(lifespan=lifespan)


@api.get("/", response_class=HTMLResponse)
async def get_bare_index(db: database.depends, templates: depends, request: Request):
    return await get_index(db, templates, request)


@api.get("/index.html", response_class=HTMLResponse)
async def get_index(db: database.depends, templates: depends, request: Request):
    if not operating_hours.open_now():
        return operating_hours.closed_index(templates, request)
    return templates.TemplateResponse(
        request,
        "index.html",
        context={"links_by_category": links.contact_links()},
    )


@api.get("/login.html", response_class=HTMLResponse)
async def get_login(
    templates: depends, request: Request, next: Annotated[str, Query()] = ""
):
    return templates.TemplateResponse(
        request, "login.html", context={"next_url": quote(next)}
    )


@api.get("/admin.html", response_class=HTMLResponse)
async def get_admin(
    db: database.depends,
    templates: depends,
    request: Request,
    _: security.authenticated,
):
    return templates.TemplateResponse(
        request,
        "admin.html",
        context={
            "links_by_category": db.contact_links.group_by_category(),
            "categories": db.link_categories.iter(),
            "active_submissions": db.contact_form_submissions.active(),
            "archived_submissions": db.contact_form_submissions.archived(),
        },
    )
