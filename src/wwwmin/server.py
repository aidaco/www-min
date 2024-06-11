from typing import Annotated
from urllib.parse import quote
import importlib.resources

import uvicorn
from fastapi import Depends, FastAPI, Form, HTTPException, Request, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from wwwmin.database import User, ContactFormSubmission
from . import security
import wwwmin.static
import wwwmin.templates


templates: Jinja2Templates
api = FastAPI()


@api.middleware("http")
async def log_request(request: Request, call_next):
    body = await request.body()
    print(f"Body: {body}")
    return await call_next(request)


@api.exception_handler(security.LoginRequired)
def handle_login_required(request: Request, _: security.LoginRequired):
    return RedirectResponse(f"/login.html?next={quote(request.url._url)}")


@api.post("/api/token")
async def submit_login(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "/admin.html",
):
    try:
        user, token = security.login_user(username, password)
    except security.AuthenticationError:
        return RedirectResponse(f"/login.html?next={next!r}", status_code=302)
    response = RedirectResponse("/admin.html", status_code=302)
    response.set_cookie(
        key="Authorization",
        value=token,
        secure=True,
        httponly=True,
        samesite="strict",
        max_age=round(security.JWT_TTL.total_seconds()),
    )
    return response


@api.post("/api/messages", status_code=201)
async def submit_message(
    email: Annotated[str, Form()],
    message: Annotated[str, Form()],
    phone: Annotated[str | None, Form()] = None,
):
    ContactFormSubmission.insert(email=email, message=message, phone=phone)
    return RedirectResponse("/", status_code=302)


@api.get("/api/messages")
async def list_messages(_: Annotated[User, Depends(security.authenticate)]):
    return ContactFormSubmission.iter()


@api.post("/api/messages/archive")
async def archive_message(
    _: Annotated[User, Depends(security.authenticate)], id: Annotated[int, Form()]
):
    message = ContactFormSubmission.get(id)
    if not message:
        raise HTTPException(404, "Not Found.")
    message.archive()
    return RedirectResponse("/admin.html", status_code=302)


@api.post("/api/messages/unarchive")
async def unarchive_message(
    _: Annotated[User, Depends(security.authenticate)], id: Annotated[int, Form()]
):
    message = ContactFormSubmission.get(id)
    if not message:
        raise HTTPException(404, "Not Found.")
    message.unarchive()
    return RedirectResponse("/admin.html", status_code=302)


@api.get("/", response_class=HTMLResponse)
def get_bare_index(request: Request):
    return get_index(request)


@api.get("/index.html", response_class=HTMLResponse)
def get_index(request: Request):
    return templates.TemplateResponse(request, "index.html", context={})


@api.get("/login.html", response_class=HTMLResponse)
def get_login(request: Request, next: Annotated[str, Query()] = ""):
    return templates.TemplateResponse(
        request, "login.html", context={"next_url": quote(next)}
    )


@api.get("/admin.html", response_class=HTMLResponse)
async def get_admin(
    request: Request, _: Annotated[User, Depends(security.authenticate)]
):
    return templates.TemplateResponse(
        request,
        "admin.html",
        context={
            "active_submissions": ContactFormSubmission.active(),
            "archived_submissions": ContactFormSubmission.archived(),
        },
    )


def serve():
    global templates
    static_files = importlib.resources.files(wwwmin.static)
    templates_files = importlib.resources.files(wwwmin.templates)
    with (
        importlib.resources.as_file(static_files) as static,
        importlib.resources.as_file(templates_files) as templates_dir,
    ):
        templates = Jinja2Templates(directory=templates_dir)
        api.mount("/", StaticFiles(directory=static), name="static")
        uvicorn.run(api)
