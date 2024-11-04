from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated, TypedDict, Unpack
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
import appbase.database

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


class UserParams(TypedDict):
    username: str
    password: str


@dataclass
class UserData:
    username: str
    password: str

    @property
    def password_hash(self) -> str:
        return hash_password(self.password)


@dataclass
class User:
    id: appbase.INTPK
    username: Annotated[str, "UNIQUE"]
    password_hash: str


class UserStore(appbase.Table[User]):
    model = User

    def by_name(self, username: str) -> User:
        return self.select().where(username=username).execute().one()

    def create_user(self, **params: Unpack[UserParams]) -> User:
        return self.insert().values(UserData(**params)).execute().one()

    def login_user(self, username: str, password: str) -> tuple[User, str]:
        user = self.by_name(username)
        if not user:
            raise AuthenticationError("User not found.")
        verify_password(user.password_hash, password)
        token = encode_token(user_id=user.id)
        return user, token


class LoginRequired(Exception):
    pass


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token", auto_error=False)


async def authenticate(
    db: database.depends,
    cookie: Annotated[str | None, Cookie(alias="Authorization")] = None,
    header: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> User | None:
    token = cookie or header
    if token is None:
        raise LoginRequired("No authorization found.")
    try:
        user_id = decode_token(token)
        return UserStore(connection=db).select().where(id=user_id).execute().one()
    except AuthenticationError:
        raise LoginRequired("Invalid authentication found.")


authenticated = Annotated[User, Depends(authenticate)]


@api.post("/api/token")
async def submit_login(
    db: database.depends, form: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    username = form.username
    password = form.password
    try:
        _, token = UserStore(connection=db).login_user(username, password)
    except AuthenticationError:
        raise HTTPException(status_code=400, detail="Authentication failed.")
    return {"access_token": token, "token_type": "bearer"}


@api.post("/form/login")
async def submit_login_form(
    db: database.depends,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "/admin.html",
):
    try:
        _, token = UserStore(connection=db).login_user(username, password)
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
    accept = request.headers.get("accept", "text/html")
    if "application/json" in accept:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    return RedirectResponse(f"/login.html?next={quote(request.url._url)}")


def install_exception_handler(app: FastAPI):
    app.exception_handler(LoginRequired)(handle_login_required)
