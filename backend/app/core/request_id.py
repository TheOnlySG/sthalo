"""Request ID propagation and request logging."""

from __future__ import annotations

import re
import time
from contextvars import ContextVar, Token
from uuid import uuid4

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_logger = structlog.get_logger("sthalo.request")


def get_request_id() -> str | None:
    """Return the current request ID, if a request is being handled."""
    return _request_id.get()


def sanitize_request_id(value: str | None) -> str:
    """Accept a bounded, log-safe caller request ID or generate a new one."""
    if value is not None and _REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return uuid4().hex


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assign a request ID, bind it to logs, and echo it in the response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = sanitize_request_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id
        token: Token[str | None] = _request_id.set(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            _logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            return response
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
            _request_id.reset(token)
