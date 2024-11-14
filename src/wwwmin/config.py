from pathlib import Path

import appbase

configconfig = appbase.config.load_from(name="wwwmin")


@configconfig.root
class config:
    datadir: Path = configconfig.source.datadir
