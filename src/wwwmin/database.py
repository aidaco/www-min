import sqlite3
from dataclasses import dataclass, field
from typing import ClassVar, Iterator, Self
from datetime import datetime, timezone
from contextlib import contextmanager

try:
    import pysqlite3 as sqlite3  # type: ignore
except Exception:
    pass

from wwwmin.util import utcnow

DB_URI = "db.sqlite3"


class TableMeta(type):
    def __new__(cls, name, bases, dct):
        inst = super().__new__(cls, name, bases, dct)
        if name != "Table":
            inst = dataclass(inst)  # type: ignore
        return inst


class Table(metaclass=TableMeta):
    database: "Database"
    CREATE_TABLE: ClassVar[str]
    INSERT_ROW: ClassVar[str]
    GET_ROW: ClassVar[str]
    ITER_ROWS: ClassVar[str]

    @classmethod
    def iter(cls) -> list[Self]:
        return [cls(**row) for row in cls.database.query(cls.ITER_ROWS)]

    @classmethod
    def create(cls, database: "Database") -> None:
        cls.database = database
        database.query(cls.CREATE_TABLE)

    @classmethod
    def insert(cls, *args, **kwargs) -> Self:
        row = cls.database.query(cls.INSERT_ROW, *args, **kwargs).fetchone()
        return cls(**row)

    @classmethod
    def get(cls, *args, **kwargs) -> Self | None:
        row = cls.database.query(cls.GET_ROW, *args, **kwargs).fetchone()
        return cls(**row) if row is not None else None


@dataclass
class Database:
    uri: str = DB_URI
    connection: sqlite3.Connection | None = None
    tables: set[type[Table]] = field(default_factory=set)

    def db(self) -> sqlite3.Connection:
        if self.connection is not None:
            return self.connection
        self.connection = sqlite3.connect(self.uri, isolation_level=None)
        self.configure_sqlite()
        self.create_tables()
        return self.connection

    def configure_sqlite(self):
        sqlite3.register_adapter(datetime, datetime.isoformat)
        sqlite3.register_converter(
            "datetime", lambda b: datetime.fromisoformat(b.decode("utf-8"))
        )
        connection = self.db()
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

    def create_tables(self):
        for table in self.tables:
            table.create(self)

    def query(self, sql: str, *args, **kwargs):
        return self.db().execute(sql, args or kwargs)

    @contextmanager
    def transact(self):
        connection = self.db()
        with connection:
            cursor = connection.cursor()
            cursor.execute("BEGIN")
            yield cursor


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
    GET_ROW: ClassVar[str] = "SELECT * FROM contact_form_submission WHERE id=:id"
    ITER_ROWS: ClassVar[str] = "SELECT * FROM contact_form_submission"
    id: int
    email: str
    message: str
    received_at: datetime
    archived_at: datetime | None = None
    phone: str | None = None

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
    GET_ROW: ClassVar[str] = "SELECT * FROM user WHERE id=:id"
    ITER_ROWS: ClassVar[str] = "SELECT * FROM user"
    id: int
    username: str
    password_hash: str

    @classmethod
    def by_name(cls, username: str) -> Self | None:
        row = cls.database.query(
            "SELECT * FROM user WHERE username=:username", username=username
        ).fetchone()
        return cls(**row) if row is not None else None
