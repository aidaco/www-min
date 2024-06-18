from contextlib import asynccontextmanager
from typing import Annotated
from importlib.resources import files, as_file
from urllib.parse import quote

from fastapi import APIRouter, Request, Depends, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from . import security, static, templates, database


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
def get_bare_index(templates: depends, request: Request):
    return get_index(templates, request)


@api.get("/index.html", response_class=HTMLResponse)
def get_index(templates: depends, request: Request):
    return templates.TemplateResponse(request, "index.html", context={})


@api.get("/login.html", response_class=HTMLResponse)
def get_login(templates: depends, request: Request, next: Annotated[str, Query()] = ""):
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
            "active_submissions": db.contact_form_submissions.active(),
            "archived_submissions": db.contact_form_submissions.archived(),
        },
    )
