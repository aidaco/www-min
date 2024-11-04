from pathlib import Path

from appbase import ConfigConfig

configconfig = ConfigConfig.load_from(name="wwwmin")


@configconfig.root
class config:
    datadir: Path = configconfig.source.datadir
