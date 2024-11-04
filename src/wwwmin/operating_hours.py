from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse
from datetime import datetime, time
import zoneinfo
import calendar
from dataclasses import field
from typing import Iterator, Annotated

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from .config import configconfig


@configconfig.section("operating_hours")
class config:
    enabled: bool = True
    schedule: dict[str, tuple[time, time] | None] = field(
        default_factory=lambda: {
            "Monday": (time(9, 0), time(17, 0)),
            "Tuesday": (time(9, 0), time(17, 0)),
            "Wednesday": (time(9, 0), time(17, 0)),
            "Thursday": (time(9, 0), time(17, 0)),
            "Friday": (time(9, 0), time(17, 0)),
            "Saturday": None,
            "Sunday": None,
        }
    )
    tz_name: str = "America/New_York"


def iter_daily_parts() -> Iterator[tuple[str, str]]:
    for day in range(7):
        day_name = calendar.day_name[day]
        match config.schedule.get(day_name):
            case [open, close]:
                o = f"{open:%l:%M%p}".strip()
                c = f"{close:%l:%M%p}".strip()
                yield day_name, f"{o}-{c}"
            case None:
                yield day_name, "Closed"


def iter_daily_as_str() -> Iterator[str]:
    for day in range(7):
        day_name = calendar.day_name[day]
        match config.schedule.get(day_name):
            case [open, close]:
                o = f"{open:%l:%M%p}".strip()
                c = f"{close:%l:%M%p}".strip()
                yield f"{day_name} {o}-{c}"
            case None:
                yield f"{day_name} Closed"


def to_simple_str() -> str:
    return ", ".join(iter_daily_as_str())


def open_now() -> bool:
    if not config.enabled:
        return True
    now = datetime.now(zoneinfo.ZoneInfo(config.tz_name))
    current_weekday = calendar.day_name[now.weekday()]
    match config.schedule[current_weekday]:
        case None:
            return False
        case (open_at, close_at):
            return open_at <= now.time() <= close_at
        case _:
            raise ValueError("Invalid config schedule value.")


def closed_index(templates: Jinja2Templates, request: Request) -> Response:
    return templates.TemplateResponse(
        request,
        "closed.html",
        {"schedule": iter_daily_parts()},
        status_code=503,
    )


def closed_json() -> JSONResponse:
    return JSONResponse(
        content={
            "status": "closed",
            "detail": f"This website is currently closed. Our operating hours are: {to_simple_str()}.",
        },
        status_code=503,
    )


class WebsiteClosedException(Exception):
    pass


async def handle_closed_exception(request: Request, _: WebsiteClosedException):
    accept = request.headers.get("accept", "text/html")
    if "application/json" in accept:
        return closed_json()
    else:
        return closed_index(request.app.state.templates, request)


def install_exception_handler(app: FastAPI):
    app.exception_handler(WebsiteClosedException)(handle_closed_exception)


async def check_open() -> bool:
    if not open_now():
        raise WebsiteClosedException()
    return True


depends = Annotated[bool, Depends(check_open)]
