from pathlib import Path

import appbase

configconfig = appbase.config.load(name="wwwmin")


@configconfig.root
class config:
    datadir: Path = getattr(configconfig.source, "datadir", None) or Path.cwd()
