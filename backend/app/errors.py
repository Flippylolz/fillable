"""Stable, content-free API error contracts; clients own presentation."""

from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

ErrorCode = Literal[
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
        status_code=status, content=ErrorEnvelope(error=detail).model_dump()
    )


def register_errors(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def application_error(_request: Request, exc: AppError):
        return error_response(exc.status, exc.detail)

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        code: ErrorCode = {404: "not_found", 405: "method_not_allowed"}.get(
            exc.status_code, "invalid_request"
        )
        return error_response(exc.status_code, ErrorDetail(code=code))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError):
        return error_response(422, ErrorDetail(code="invalid_request"))

    @app.exception_handler(Exception)
    async def unexpected_error(_request: Request, _exc: Exception):
        return error_response(500, ErrorDetail(code="internal_error"))
