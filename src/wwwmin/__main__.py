from pathlib import Path
from typing import Literal, cast
import cyclopts
from rich.console import Console

console = Console()
main = cli = cyclopts.App(name="wwwmin-serve")
config_cli = cyclopts.App(name="config")
user_cli = cyclopts.App(name="user")
cli.command(user_cli)
cli.command(config_cli)


@cli.default()
@cli.command()
def serve():
    import wwwmin.server

    wwwmin.server.serve()


@config_cli.command()
def show(format: Literal["json", "toml", "yaml"] = "toml"):
    import wwwmin.server
    import wwwmin.config

    console.print(wwwmin.config.configconfig.dumps(format), markup=False)


@config_cli.command()
def init(path: Path | None = None):
    import wwwmin.server
    import wwwmin.config

    path = path or wwwmin.config.configconfig.source.configdir / "config.toml"
    format = path.suffix.lstrip(".").lower()
    if format not in {"toml", "yaml", "json"}:
        raise ValueError(f"Unsupported config format: {format}")
    format = cast(Literal["toml", "json", "yaml"], format)
    path.parent.mkdir(exist_ok=True)
    path.write_text(wwwmin.config.configconfig.dumps(format))


@user_cli.command()
def create(username: str, password: str) -> None:
    import wwwmin.security

    console.print(wwwmin.security.User.create(username, password))


@user_cli.command()
def list() -> None:
    import wwwmin.security

    console.print(*wwwmin.security.User.iterall(), sep="\n")


if __name__ == "__main__":
    cli()
