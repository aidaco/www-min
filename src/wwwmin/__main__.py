from . import server, database
from rich import print


def main():
    try:
        with database.WWWMINDatabase() as db:
            server.serve()
    except KeyboardInterrupt:
        print("[red]Stopped.[/]")


if __name__ == "__main__":
    main()
