from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from datetime import datetime, time
import zoneinfo
import calendar
from dataclasses import field

from .config import config as main_config


@main_config.section("operating_hours")
class config:
    operating_hours: dict[str, tuple[time, time] | None] = field(
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


async def check_open_hours(request: Request, call_next):
    now = datetime.now(zoneinfo.ZoneInfo(config.tz_name))
    current_weekday = calendar.day_name[now.weekday()]
    match config.operating_hours[current_weekday]:
        case None:
            is_open = False
            print(f"we are open: {is_open}")
        case (open_at, close_at):
            is_open = open_at <= now.time() <= close_at

    print(f"open status: {is_open}")
    if not is_open:
        accepted_content = request.headers.get("accept", "")

        if "application/json" in accepted_content:
            return JSONResponse(
                content={
                    "detail": "We are currently closed. Our operating hours are from 9 AM to 5 PM EST/EDT, Monday to Friday."
                },
                status_code=503,
            )
        else:
            return HTMLResponse("we are closed", status_code=503)
    response = await call_next(request)
    return response
