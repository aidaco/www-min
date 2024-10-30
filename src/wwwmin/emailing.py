import sys
import smtplib
import email.message

from fastapi import Request, FastAPI
from fastapi.responses import PlainTextResponse

from .config import config as main_config
from . import database


@main_config.section("emailing")
class config:
    enabled: bool = False
    host: str = ""
    port: int = 0
    username: str = ""
    password: str = ""
    to: str = ""


async def notify_submission(submission: database.ContactFormSubmission):
    msg = email.message.EmailMessage()
    msg["From"] = config.username
    msg["To"] = config.to
    msg["Subject"] = (
        f'Contact Submission [{submission.id}] from [{submission.email or ""}|{submission.phone or ""}] at [{submission.received_at}]'
    )
    msg.set_content(submission.message)
    await notify(msg)


async def notify_exception(host, port, method, url, exc_type, exc_value, exc_tb):
    msg = email.message.EmailMessage()
    msg["From"] = config.username
    msg["To"] = config.to
    msg["Subject"] = f'{host}:{port} - "{method} {url}" <{exc_type}: {exc_value}>'
    msg.set_content(f"{exc_tb}")
    await notify(msg)


async def notify(msg: email.message.EmailMessage):
    if not config.enabled:
        return
    with smtplib.SMTP(config.host, config.port) as smtp:
        smtp.starttls()
        smtp.login(config.username, config.password)
        smtp.send_message(msg)


async def notify_unhandled_exceptions_handler(
    request: Request, exc: Exception
) -> PlainTextResponse:
    """
    This middleware will log all unhandled exceptions.
    Unhandled exceptions are all exceptions that are not HTTPExceptions or RequestValidationErrors.
    """
    host = getattr(getattr(request, "client", None), "host", None)
    port = getattr(getattr(request, "client", None), "port", None)
    url = (
        f"{request.url.path}?{request.query_params}"
        if request.query_params
        else request.url.path
    )
    exception_type, exception_value, exception_traceback = sys.exc_info()
    await notify_exception(
        host,
        port,
        request.method,
        url,
        exception_type,
        exception_value,
        exception_traceback,
    )
    return PlainTextResponse(str(exc), status_code=500)


def install_exception_handler(app: FastAPI):
    app.exception_handler(Exception)(notify_unhandled_exceptions_handler)
