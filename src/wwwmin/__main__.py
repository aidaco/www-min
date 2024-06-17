from . import server
from rich import print


def main():
    try:
        server.serve()
    except KeyboardInterrupt:
        print("[red]Stopped.[/]")


if __name__ == "__main__":
    main()
