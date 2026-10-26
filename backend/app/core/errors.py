"""Application errors and the stable API error envelope."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from http import HTTPStatus
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_id import REQUEST_ID_HEADER, get_request_id

_logger = structlog.get_logger("sthalo.error")


class ErrorCode(StrEnum):
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    SLOT_UNAVAILABLE = "SLOT_UNAVAILABLE"
    HOLD_EXPIRED = "HOLD_EXPIRED"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    VEHICLE_DOES_NOT_FIT = "VEHICLE_DOES_NOT_FIT"
    OWN_LISTING = "OWN_LISTING"
    LISTING_NOT_ACTIVE = "LISTING_NOT_ACTIVE"
    INCOMPLETE_LISTING = "INCOMPLETE_LISTING"
    HAS_FUTURE_BOOKINGS = "HAS_FUTURE_BOOKINGS"
    BLOCK_CONFLICTS_BOOKING = "BLOCK_CONFLICTS_BOOKING"
    IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
    RATE_LIMITED = "RATE_LIMITED"
    UPLOAD_INVALID = "UPLOAD_INVALID"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    HTTP_ERROR = "HTTP_ERROR"


class AppError(Exception):
    """A handled application error that maps to the public error envelope."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int = 400,
        details: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []
        self.headers = headers or {}


def error_response(
    *,
    status_code: int,
    code: ErrorCode,
    message: str,
    details: list[dict[str, Any]] | None = None,
    headers: Mapping[str, str] | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    """Build the documented `{"error": {...}}` response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code.value,
                "message": message,
                "details": details or [],
                "request_id": request_id or get_request_id() or "unavailable",
            }
        },
        headers=headers,
    )


def _default_http_code(status_code: int) -> ErrorCode:
    return {
        401: ErrorCode.UNAUTHENTICATED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        422: ErrorCode.VALIDATION_ERROR,
        429: ErrorCode.RATE_LIMITED,
    }.get(status_code, ErrorCode.HTTP_ERROR)


def _http_message(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "HTTP error"


async def handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        return await handle_unhandled_exception(request, exc)
    _logger.warning(
        "application_error",
        error_code=exc.code.value,
        status_code=exc.status_code,
        path=request.url.path,
        method=request.method,
    )
    request_id = _request_id_from(request)
    return error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        headers={**(exc.headers or {}), REQUEST_ID_HEADER: request_id},
        request_id=request_id,
    )


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        return await handle_unhandled_exception(request, exc)

    details = [
        {
            "field": ".".join(str(part) for part in error.get("loc", ())),
            "message": str(error.get("msg", "Invalid value")),
            "type": str(error.get("type", "value_error")),
        }
        for error in exc.errors()
    ]
    _logger.warning(
        "request_validation_failed",
        path=request.url.path,
        method=request.method,
        error_count=len(details),
    )
    request_id = _request_id_from(request)
    return error_response(
        status_code=422,
        code=ErrorCode.VALIDATION_ERROR,
        message="Request validation failed.",
        details=details,
        request_id=request_id,
    )


async def handle_http_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        return await handle_unhandled_exception(request, exc)

    code = _default_http_code(exc.status_code)
    message = _http_message(exc.status_code)
    details: list[dict[str, Any]] = []

    if isinstance(exc.detail, dict):
        raw_code = exc.detail.get("code")
        if isinstance(raw_code, str):
            try:
                code = ErrorCode(raw_code)
            except ValueError:
                code = ErrorCode.HTTP_ERROR
        raw_message = exc.detail.get("message")
        if isinstance(raw_message, str) and raw_message:
            message = raw_message
        raw_details = exc.detail.get("details")
        if isinstance(raw_details, list):
            details = [item for item in raw_details if isinstance(item, dict)]
    elif exc.detail:
        message = str(exc.detail)

    _logger.warning(
        "http_error",
        error_code=code.value,
        status_code=exc.status_code,
        path=request.url.path,
        method=request.method,
    )
    request_id = _request_id_from(request)
    return error_response(
        status_code=exc.status_code,
        code=code,
        message=message,
        details=details,
        headers={**(exc.headers or {}), REQUEST_ID_HEADER: request_id},
        request_id=request_id,
    )


async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id_from(request)
    _logger.exception(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
        request_id=request_id,
    )
    return error_response(
        status_code=500,
        code=ErrorCode.INTERNAL_ERROR,
        message="An unexpected error occurred.",
        headers={REQUEST_ID_HEADER: request_id},
        request_id=request_id,
    )


def _request_id_from(request: Request) -> str:
    return get_request_id() or getattr(request.state, "request_id", None) or "unavailable"


def register_exception_handlers(app: FastAPI) -> None:
    """Install handlers that keep every error JSON-shaped and traceable."""
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_error)
    app.add_exception_handler(Exception, handle_unhandled_exception)
