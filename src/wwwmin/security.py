from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated, Any, Self
from urllib.parse import quote

import jwt
import argon2
from fastapi import (
    APIRouter,
    Cookie,
    FastAPI,
    HTTPException,
    Form,
    Request,
    Depends,
)
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import appbase
from appbase.database import Table

from .util import utcnow
from . import database
from .config import configconfig


@configconfig.section("security")
class config:
    jwt_secret: str = "correct horse battery staple"
    jwt_ttl: timedelta = timedelta(days=30)


api = APIRouter()
hasher = argon2.PasswordHasher()


class AuthenticationError(Exception):
    pass


def _hash_password(password: str) -> str:
    return hasher.hash(password)


def _verify_password(hash: str, password: str) -> bool:
    try:
        return hasher.verify(hash, password)
    except argon2.exceptions.VerificationError:
        raise AuthenticationError("Password mismatch.")


def _encode_token(user_id: int, scopes: set[str] | None = None) -> str:
    return jwt.encode(
        {
            "user": user_id,
            "scopes": ";".join(scopes) if scopes else "",
            "exp": utcnow() + config.jwt_ttl,
        },
        key=config.jwt_secret,
        algorithm="HS256",
    )


def _decode_token(token: str) -> tuple[int, set[str] | None]:
    try:
        data = jwt.decode(token, key=config.jwt_secret, algorithms=["HS256"])["user"]
        user_id = int(data["user"])
        scopes = data["scopes"]
        scopes = set(scopes.split(";")) if scopes != "" else None
        return user_id, scopes
    except (jwt.DecodeError, AttributeError):
        raise AuthenticationError("Invalid token.")


@dataclass
class UserData:
    username: str
    password: str

    @property
    def password_hash(self) -> str:
        return _hash_password(self.password)


@dataclass
class User:
    id: appbase.database.INTPK
    username: Annotated[str, "UNIQUE"]
    password_hash: str

    @classmethod
    def get_by_id(cls, id: int) -> Self | None:
        table = Table(cls)
        return (
            table.select().where(id=id).execute(table.cursor(database.connection)).one()
        )

    @classmethod
    def get_by_name(cls, username: str) -> Self | None:
        table = Table(cls)
        return (
            table.select()
            .where(username=username)
            .execute(table.cursor(database.connection))
            .one()
        )

    @classmethod
    def create(cls, username: str, password: str) -> Self | None:
        table = Table(cls)
        return (
            table.insert()
            .values(UserData(username=username, password=password))
            .execute(table.cursor(database.connection))
            .one()
        )

    @classmethod
    def authenticate_password(cls, username: str, password: str) -> Self:
        user = cls.get_by_name(username)
        if not user:
            raise AuthenticationError("User not found.")
        _verify_password(user.password_hash, password)
        return user

    @classmethod
    def authenticate_token(cls, token: Any) -> Self:
        if not isinstance(token, str):
            raise AuthenticationError("No authentication found.")
        user_id, scopes = _decode_token(token)
        user = cls.get_by_id(user_id)
        if not user:
            raise AuthenticationError("User not found.")
        return user

    def encode_token(self, scopes: set[str] | None = None) -> str:
        return _encode_token(self.id, scopes)


class LoginRequired(Exception):
    pass


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token", auto_error=False)


async def authenticate(
    cookie: Annotated[str | None, Cookie(alias="Authorization")] = None,
    header: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> User | None:
    try:
        return User.authenticate_token(cookie or header)
    except AuthenticationError:
        raise LoginRequired("Invalid authentication found.")


authenticated = Annotated[User, Depends(authenticate)]


@api.post("/api/token")
async def submit_login(form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    username = form.username
    password = form.password
    try:
        user = User.authenticate_password(username, password)
    except AuthenticationError:
        raise HTTPException(status_code=400, detail="Authentication failed.")
    return {"access_token": user.encode_token(), "token_type": "bearer"}


@api.post("/form/login")
async def submit_login_form(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "/admin.html",
):
    try:
        user = User.authenticate_password(username, password)
    except AuthenticationError:
        return RedirectResponse(f"/login.html?next={next!r}", status_code=302)
    response = RedirectResponse("/admin.html", status_code=302)
    response.set_cookie(
        key="Authorization",
        value=user.encode_token(),
        secure=True,
        httponly=True,
        samesite="strict",
        max_age=round(config.jwt_ttl.total_seconds()),
    )
    return response


def handle_login_required(request: Request, _: LoginRequired):
    accept = request.headers.get("accept", "text/html")
    if "application/json" in accept:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    return RedirectResponse(f"/login.html?next={quote(request.url._url)}")


def install_exception_handler(app: FastAPI):
    app.exception_handler(LoginRequired)(handle_login_required)
