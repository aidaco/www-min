from pathlib import Path

import appbase

from wwwmin.config import configconfig, config as main_config


@configconfig.section("database")
class config:
    uri: Path | str = main_config.datadir / "database.sqlite3"
    echo: bool = False


connection = appbase.database.connect(config.uri, echo=config.echo)
