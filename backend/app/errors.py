"""Stable, content-free API error contracts; clients own presentation."""

import logging
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

ErrorCode = Literal[
    "invalid_document",
    "unsupported_document",
    "document_limit",
    "quota_exceeded",
    "file_too_large",
    "storage_unavailable",
    "operation_conflict",
    "operation_in_progress",
    "operation_aborted",
    "upload_busy",
    "upload_timeout",
    "current_password_invalid",
    "authentication_required",
    "invalid_credentials",
    "forbidden",
    "rate_limited",
    "account_exists",
    "dependencies_unavailable",
    "not_found",
    "method_not_allowed",
    "invalid_request",
    "internal_error",
]


class ErrorDetail(BaseModel):
    code: ErrorCode
    parameters: dict[str, str | int] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class AppError(Exception):
    def __init__(
        self,
        status: int,
        code: ErrorCode,
        parameters: dict[str, str | int] | None = None,
    ):
        self.status = status
        self.detail = ErrorDetail(code=code, parameters=parameters or {})


def error_response(status: int, detail: ErrorDetail) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorEnvelope(error=detail).model_dump(),
        headers={"Cache-Control": "no-store"},
    )


class SanitizedErrors:
    """Do not pass untrusted exception messages/chains to the server logger."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def outgoing(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, outgoing)
        except Exception:
            pass
        else:
            return
        # Leave the exception context before sending or raising: even a transport
        # failure must not acquire the original exception as an implicit chain.
        logging.getLogger("fillable.errors").error("request_failed")
        if started:
            raise RuntimeError("request_failed") from None
        await error_response(500, ErrorDetail(code="internal_error"))(
            scope, receive, send
        )


def register_errors(app: FastAPI) -> None:
    app.add_middleware(SanitizedErrors)

    @app.exception_handler(AppError)
    async def application_error(_request: Request, exc: AppError):
        return error_response(exc.status, exc.detail)

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        codes: dict[int, ErrorCode] = {404: "not_found", 405: "method_not_allowed"}
        code = codes.get(exc.status_code, "invalid_request")
        return error_response(exc.status_code, ErrorDetail(code=code))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        return error_response(
            422,
            ErrorDetail(code="invalid_request", parameters=validation_parameters(exc)),
        )


def validation_parameters(exc: RequestValidationError) -> dict[str, str | int]:
    """Report the offending parameter's name and machine reason only.

    Submitted values, exception text and internal messages never leave the
    server; hostile or oversized request-supplied names are bounded.
    """
    for error in exc.errors():
        name = next(
            (part for part in reversed(error.get("loc", ())) if isinstance(part, str)),
            None,
        )
        cleaned = "".join(
            char
            for char in (name or "")[:64]
            if char.isprintable() and not char.isspace()
        )
        if not cleaned:
            continue
        return {"parameter": cleaned, "reason": str(error.get("type", "invalid"))[:64]}
    return {}
