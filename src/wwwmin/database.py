import sqlite3
from typing import Annotated

from fastapi import Depends, Request


from wwwmin.config import configconfig, config as main_config


@configconfig.section("database")
class config:
    uri: str = str(main_config.datadir / "database.sqlite3")


def _depends_database(request: Request) -> sqlite3.Connection:
    return request.app.state.db


depends = Annotated[sqlite3.Connection, Depends(_depends_database)]
