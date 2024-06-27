from typing import Literal
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

    console.print(wwwmin.config.config.dumps(format), markup=False)


@user_cli.command()
def create(username: str, password: str) -> None:
    import wwwmin.security

    console.print(wwwmin.security.create_user(username, password))


@user_cli.command()
def list() -> None:
    import wwwmin.database

    console.print(wwwmin.database.database.users.iter())


if __name__ == "__main__":
    cli()
