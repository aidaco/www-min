from contextlib import asynccontextmanager
from typing import Annotated
from importlib.resources import files, as_file
from urllib.parse import quote

from fastapi import APIRouter, Request, Depends, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from . import security, static, templates, database, operating_hours, links, submissions


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
async def get_bare_index(
    templates: depends,
    request: Request,
    operating: operating_hours.depends,
):
    return await get_index(templates, request, operating)


@api.get("/index.html", response_class=HTMLResponse)
async def get_index(
    templates: depends,
    request: Request,
    _: operating_hours.depends,
):
    return templates.TemplateResponse(
        request,
        "index.html",
        context={"links_by_category": links.get_contact_links()},
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
    templates: depends,
    request: Request,
    _: security.authenticated,
):
    return templates.TemplateResponse(
        request,
        "admin.html",
        context={
            "links_by_category": links.ContactLink.group_by_category(),
            "categories": database.connection.table(links.LinkCategory)
            .select()
            .execute()
            .all(),
            "active_submissions": submissions.ContactFormSubmission.active(),
            "archived_submissions": submissions.ContactFormSubmission.archived(),
        },
    )
