import sqlite3
from dataclasses import dataclass, field
from typing import Annotated, ClassVar, Iterator, Self, Protocol
from datetime import datetime, timezone
from contextlib import asynccontextmanager, contextmanager
import json
import re
from functools import cache

from fastapi import Depends, Request


try:
    import pysqlite3 as sqlite3  # type: ignore
except Exception:
    pass

from wwwmin.util import utcnow

DB_URI = "db.sqlite3"


class TableMeta(type):
    database: "Database"

    def __new__(cls, name, bases, dct, init=True):
        inst = super().__new__(cls, name, bases, dct)
        if init:
            inst = dataclass(inst)  # type: ignore
        return inst

    def __get__(cls, owner, owner_cls):
        return type(
            f"BoundTable<{cls.__name__}>",
            (cls,),
            {
                "database": owner,
                "NAME": getattr(cls, "NAME", owner_cls.default_name(cls)),
            },
        )


class Table(metaclass=TableMeta, init=False):
    database: "Database"
    NAME: str
    CREATE_TABLE: ClassVar[str]
    INSERT_ROW: ClassVar[str]
    GET_ROW: ClassVar[str] = "SELECT * FROM {name} WHERE id=:id"
    ITER_ROWS: ClassVar[str] = "SELECT * FROM {name}"

    @classmethod
    def parse(cls, row: sqlite3.Row) -> Self:
        return cls(**row)

    @classmethod
    def iter(cls) -> list[Self]:
        return [
            cls.parse(row)
            for row in cls.database.query(cls.ITER_ROWS.format(name=cls.NAME))
        ]

    @classmethod
    def create(cls) -> None:
        cls.database.query(cls.CREATE_TABLE)

    @classmethod
    def insert(cls, *args, **kwargs) -> Self:
        row = cls.database.query(cls.INSERT_ROW, *args, **kwargs).fetchone()
        return cls(**row)

    @classmethod
    def get(cls, *args, **kwargs) -> Self | None:
        row = cls.database.query(cls.GET_ROW, *args, **kwargs).fetchone()
        return cls(**row) if row is not None else None


class DatabaseMeta(type):
    def __new__(cls, name, bases, dct):
        inst = super().__new__(cls, name, bases, dct)
        inst = dataclass(inst)  # type: ignore
        return inst

    def __init__(cls, name, bases, dct):
        super().__init__(cls)


class Database(metaclass=DatabaseMeta):
    uri: str
    _connection: sqlite3.Connection | None = None

    @property
    def tables(self):
        cls = type(self)
        return [
            getattr(self, key)
            for key, value in vars(cls).items()
            if isinstance(value, TableMeta)
        ]

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection or self.connect() or self._connection

    def connect(self):
        self._connection = sqlite3.connect(self.uri, isolation_level=None)
        self.configure_sqlite()
        self.create_tables()

    def configure_sqlite(self):
        sqlite3.register_adapter(datetime, datetime.isoformat)
        sqlite3.register_converter(
            "datetime", lambda b: datetime.fromisoformat(b.decode("utf-8"))
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            pragma journal_mode = WAL;
            pragma synchronous = normal;
            pragma temp_store = memory;
            pragma mmap_size = 30000000000;
            pragma foreign_keys = on;
            pragma auto_vacuum = incremental;
            pragma foreign_keys = on;
        """)

    @classmethod
    def default_name(
        cls, table: type[Table], replace_regex=re.compile("(?<!^)(?=[A-Z])")
    ) -> str:
        return replace_regex.sub("_", table.__name__).lower()

    def create_tables(self):
        for table in self.tables:
            table.create()

    def query(self, sql: str, *args, **kwargs):
        return self.connection.execute(sql, args or kwargs)

    @contextmanager
    def transact(self):
        with self.connection:
            cursor = self.connection.cursor()
            cursor.execute("BEGIN")
            yield cursor

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.connection.close()


class ContactFormSubmission(Table):
    CREATE_TABLE: ClassVar[str] = """
        CREATE TABLE IF NOT EXISTS contact_form_submission(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            message TEXT NOT NULL,
            phone TEXT,
            received_at DATETIME NOT NULL,
            archived_at DATETIME
        )
    """
    INSERT_ROW: ClassVar[str] = """
        INSERT INTO contact_form_submission(
            email, message, phone, received_at, archived_at
        ) 
        VALUES (:email, :message, :phone, :received_at, :archived_at)
        RETURNING *
    """
    email: str
    message: str
    received_at: datetime = field(default_factory=utcnow)
    archived_at: datetime | None = None
    phone: str | None = None
    id: int | None = None

    @classmethod
    def insert(
        cls,
        email: str,
        message: str,
        phone: str | None = None,
        received_at: datetime | None = None,
        archived_at: datetime | None = None,
    ) -> Self:
        return super().insert(
            email=email,
            message=message,
            phone=phone,
            received_at=received_at if received_at is not None else utcnow(),
            archived_at=archived_at,
        )

    def archive(self) -> Self:
        cls = type(self)
        return cls(
            **self.database.query(
                "UPDATE contact_form_submission SET archived_at=:archived_at WHERE id=:id RETURNING *",
                archived_at=utcnow(),
                id=self.id,
            ).fetchone()
        )

    def unarchive(self) -> Self:
        cls = type(self)
        return cls(
            **self.database.query(
                "UPDATE contact_form_submission SET archived_at=NULL WHERE id=:id RETURNING *",
                id=self.id,
            ).fetchone()
        )

    @classmethod
    def archived(cls) -> list[Self]:
        return [
            cls(**row)
            for row in cls.database.query(
                "SELECT * FROM contact_form_submission WHERE archived_at IS NOT NULL ORDER BY archived_at DESC"
            )
        ]

    @classmethod
    def active(cls) -> list[Self]:
        return [
            cls(**row)
            for row in cls.database.query(
                "SELECT * FROM contact_form_submission WHERE archived_at IS NULL ORDER BY received_at DESC"
            )
        ]


class User(Table):
    CREATE_TABLE: ClassVar[str] = """
        CREATE TABLE IF NOT EXISTS user(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL
        )
    """
    INSERT_ROW: ClassVar[str] = """
        INSERT INTO user(username, password_hash) 
        VALUES (:username, :password)
        RETURNING *
    """
    id: int
    username: str
    password_hash: str

    @classmethod
    def by_name(cls, username: str) -> Self | None:
        row = cls.database.query(
            "SELECT * FROM user WHERE username=:username", username=username
        ).fetchone()
        return cls(**row) if row is not None else None


class WebPushSubscription(Table):
    CREATE_TABLE: ClassVar[str] = """
        CREATE TABLE IF NOT EXISTS web_push_subscription(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES user(id) ON UPDATE CASCADE ON DELETE CASCADE,
            subscription JSONB NOT NULL,
            subscribed_at DATETIME NOT NULL
        )
    """
    INSERT_ROW: ClassVar[str] = """
        INSERT INTO web_push_subscription(user_id, subscription, subscribed_at) 
        VALUES (:user_id, :subscription, :subscribed_at)
        RETURNING *
    """
    id: int
    user_id: int
    subscription: str
    subscribed_at: datetime

    @classmethod
    def insert(
        cls,
        user_id: int,
        subscription: dict,
        subscribed_at: datetime | None = None,
    ) -> Self:
        return super().insert(
            user_id=user_id,
            subscription=json.dumps(subscription).encode(),
            subscribed_at=subscribed_at if subscribed_at is not None else utcnow(),
        )

    @classmethod
    def by_user_id(cls, user_id: int) -> Self | None:
        row = cls.database.query(
            "SELECT * FROM web_push_subscription WHERE user_id=:user_id",
            user_id=user_id,
        ).fetchone()
        return cls(**row) if row is not None else None


class WWWMINDatabase(Database):
    uri: str = DB_URI
    contact_form_submissions = ContactFormSubmission
    users = User
    web_push_subscription = WebPushSubscription


@asynccontextmanager
async def lifespan(app):
    app.state.database = inst = WWWMINDatabase()
    with inst:
        yield


async def _depend_on_database(request: Request):
    return request.app.state.database


depends = Annotated[WWWMINDatabase, Depends(_depend_on_database)]
