from typing import Annotated, ClassVar, Iterator, Self
import sqlite3
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from urllib.parse import quote

import jwt
import argon2
import uvicorn
from fastapi import Cookie, Depends, FastAPI, Form, Header, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

DB_URI = "db.sqlite3"
JWT_SECRET = "correct horse battery staple"
JWT_TTL = timedelta(days=30)

hasher = argon2.PasswordHasher()
templates = Jinja2Templates(directory="templates")


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(hash: str, password: str) -> bool:
    try:
        return hasher.verify(hash, password)
    except argon2.exceptions.VerificationError:
        raise AuthenticationError("Password mismatch.")


def encode_token(user_id: int) -> str:
    return jwt.encode(
        {"user": user_id, "exp": utcnow() + JWT_TTL}, key=JWT_SECRET, algorithm="HS256"
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, key=JWT_SECRET, algorithms=["HS256"])["user"]
    except jwt.DecodeError:
        raise AuthenticationError("Invalid token.")


_connection: sqlite3.Connection


def db() -> sqlite3.Connection:
    global _connection
    try:
        return _connection
    except NameError:
        _connection = sqlite3.connect(DB_URI, isolation_level=None)
        configure_sqlite(_connection)
        create_tables(_connection)
        return _connection


def query(sql: str, *args, **kwargs):
    return db().execute(sql, *args, **kwargs)


def configure_sqlite(connection: sqlite3.Connection):
    sqlite3.register_adapter(datetime, datetime.isoformat)
    sqlite3.register_converter(
        "datetime", lambda b: datetime.fromisoformat(b.decode("utf-8"))
    )
    connection.row_factory = sqlite3.Row
    connection.executescript("""
        pragma journal_mode = WAL;
        pragma synchronous = normal;
        pragma temp_store = memory;
        pragma mmap_size = 30000000000;
        pragma foreign_keys = on;
        pragma auto_vacuum = incremental;
        pragma foreign_keys = on;
    """)


def create_tables(connection: sqlite3.Connection):
    connection.execute(ContactFormSubmission.CREATE_TABLE)
    connection.execute(User.CREATE_TABLE)


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class ContactFormSubmission:
    CREATE_TABLE: ClassVar[str] = """
        CREATE TABLE IF NOT EXISTS contact_form_submission(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            message TEXT NOT NULL,
            phone TEXT,
            received_at DATETIME NOT NULL 
        )
    """
    INSERT_ROW: ClassVar[str] = """
        INSERT INTO contact_form_submission(
            email, phone, message, received_at
        ) 
        VALUES (?, ?, ?, ?)
        RETURNING *
    """
    id: int
    email: str
    message: str
    phone: str | None = None
    received_at: datetime = field(default_factory=utcnow)

    @classmethod
    def insert(
        cls,
        email: str,
        message: str,
        phone: str | None = None,
        received_at: datetime | None = None,
    ) -> Self:
        row = query(
            cls.INSERT_ROW,
            (email, message, phone, received_at),
        ).fetchone()
        return cls(**row)

    @classmethod
    def list(cls) -> list[Self]:
        return [cls(**row) for row in query("SELECT * FROM contact_form_submission")]


@dataclass
class User:
    CREATE_TABLE: ClassVar[str] = """
        CREATE TABLE IF NOT EXISTS user(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL
        )
    """
    INSERT_ROW: ClassVar[str] = """
        INSERT INTO user(username, password_hash) 
        VALUES (?, ?)
        RETURNING *
    """
    id: int
    username: str
    password_hash: str

    @classmethod
    def insert(cls, username: str, password: str) -> Self:
        password_hash = hash_password(password)
        row = query(
            cls.INSERT_ROW,
            (username, password_hash),
        ).fetchone()
        return cls(**row)


class AuthenticationError(Exception):
    pass


class LoginRequired(Exception):
    pass


def login_user(username: str, password: str) -> tuple[User, str]:
    row = query("SELECT * FROM user WHERE username=?", (username,)).fetchone()
    if not row:
        raise AuthenticationError("User not found.")
    user = User(**row)
    verify_password(user.password_hash, password)
    token = encode_token(user_id=user.id)
    return user, token


api = FastAPI()


def authenticate(
    cookie: Annotated[str | None, Cookie(alias="Authorization")],
    header: Annotated[str | None, Header(alias="Authorization")],
) -> User | None:
    token = cookie or header
    if token is None:
        raise LoginRequired("No authorization found.")
    try:
        user_id = decode_token(token)["user"]
        return User(**query("SELECT * FROM user WHERE id=?", (user_id,)).fetchone())
    except AuthenticationError:
        raise LoginRequired("Invalid authentication found.")


@api.exception_handler(LoginRequired)
def handle_login_required(request: Request, _: LoginRequired):
    return RedirectResponse(f"/login?next={quote(request.url._url)}")


@api.post("/api/token")
def submit_login(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()],
):
    try:
        user, token = login_user(username, password)
    except AuthenticationError:
        return RedirectResponse(f"/login?next={next!r}")
    response = RedirectResponse("/admin", status_code=302)
    response.set_cookie(
        key="Authorization",
        value=token,
        secure=True,
        httponly=True,
        samesite="strict",
        max_age=round(JWT_TTL.total_seconds()),
    )
    return response


@api.post("/api/messages", status_code=201)
def submit_message(
    email: Annotated[str, Form()],
    message: Annotated[str, Form()],
    phone: Annotated[str | None, Form()] = None,
):
    ContactFormSubmission.insert(email, message, phone)


@api.get("/api/messages")
def list_messages(_: Annotated[User, Depends(authenticate)]):
    return ContactFormSubmission.list()


@api.get("/", response_class=HTMLResponse)
def get_bare_index(request: Request):
    return get_index(request)


@api.get("/index.html", response_class=HTMLResponse)
def get_index(request: Request):
    return templates.TemplateResponse(request, "index.html", context={})


@api.get("/login.html", response_class=HTMLResponse)
def get_login(request: Request):
    return templates.TemplateResponse(request, "login.html", context={})


@api.get("/admin.html", response_class=HTMLResponse)
def get_admin(request: Request, _: Annotated[User, Depends(authenticate)]):
    return templates.TemplateResponse(
        request,
        "admin.html",
        context={"contact_form_submissions": ContactFormSubmission.list()},
    )


api.mount("/", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    uvicorn.run(api)
