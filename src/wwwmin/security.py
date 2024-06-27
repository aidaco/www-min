from datetime import timedelta
from typing import Annotated
from urllib.parse import quote

import jwt
import argon2
from fastapi import (
    APIRouter,
    Cookie,
    FastAPI,
    HTTPException,
    Header,
    Form,
    Request,
    Depends,
)
from fastapi.responses import RedirectResponse

from .util import utcnow
from . import database
from .config import config as main_config


@main_config.section("security")
class config:
    jwt_secret: str = "correct horse battery staple"
    jwt_ttl: timedelta = timedelta(days=30)


api = APIRouter()
hasher = argon2.PasswordHasher()


class AuthenticationError(Exception):
    pass


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(hash: str, password: str) -> bool:
    try:
        return hasher.verify(hash, password)
    except argon2.exceptions.VerificationError:
        raise AuthenticationError("Password mismatch.")


def encode_token(user_id: int) -> str:
    return jwt.encode(
        {"user": user_id, "exp": utcnow() + config.jwt_ttl},
        key=config.jwt_secret,
        algorithm="HS256",
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, key=config.jwt_secret, algorithms=["HS256"])["user"]
    except jwt.DecodeError:
        raise AuthenticationError("Invalid token.")


def create_user(username: str, password: str) -> database.User:
    password_hash = hash_password(password)
    return database.database.users.insert(username, password_hash)


def login_user(username: str, password: str) -> tuple[database.User, str]:
    user = database.database.users.by_name(username)
    if not user:
        raise AuthenticationError("User not found.")
    verify_password(user.password_hash, password)
    token = encode_token(user_id=user.id)
    return user, token


class LoginRequired(Exception):
    pass


async def authenticate(
    db: database.depends,
    cookie: Annotated[str | None, Cookie(alias="Authorization")] = None,
    header: Annotated[str | None, Header(alias="Authorization")] = None,
) -> database.User | None:
    token = cookie or header
    if token is None:
        raise LoginRequired("No authorization found.")
    try:
        user_id = decode_token(token)
        return db.users.get(user_id)
    except AuthenticationError:
        raise LoginRequired("Invalid authentication found.")


authenticated = Annotated[database.User, Depends(authenticate)]


@api.post("/api/token")
async def submit_login(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    try:
        _, token = login_user(username, password)
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Authentication failed.")
    return {"token": token}


@api.post("/form/login")
async def submit_login_form(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "/admin.html",
):
    try:
        _, token = login_user(username, password)
    except AuthenticationError:
        return RedirectResponse(f"/login.html?next={next!r}", status_code=302)
    response = RedirectResponse("/admin.html", status_code=302)
    response.set_cookie(
        key="Authorization",
        value=token,
        secure=True,
        httponly=True,
        samesite="strict",
        max_age=round(config.jwt_ttl.total_seconds()),
    )
    return response


def handle_login_required(request: Request, _: LoginRequired):
    return RedirectResponse(f"/login.html?next={quote(request.url._url)}")


def install_exception_handler(app: FastAPI):
    app.exception_handler(LoginRequired)(handle_login_required)
