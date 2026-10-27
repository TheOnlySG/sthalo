"""Security headers and lightweight per-client rate limiting."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import Environment, Settings
from app.core.errors import ErrorCode, error_response


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    """A request budget for one API path prefix."""

    prefix: str
    bucket: str
    limit: int


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply in-process sliding-window limits to API requests.

    The state is per process. Hosted deployments with more than one worker should
    replace this with a shared store such as Redis, but the free single-instance
    demo intentionally keeps the dependency footprint at zero.
    """

    _MAX_TRACKED_CLIENTS = 10_000

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        super().__init__(app)
        self.enabled = settings.rate_limit_enabled
        self.window = settings.rate_limit_window_seconds
        self.trust_proxy = settings.rate_limit_trust_proxy
        self.rules = (
            RateLimitRule("/api/v1/reservations", "booking", settings.rate_limit_booking_requests),
            RateLimitRule("/api/v1/search", "read", settings.rate_limit_read_requests),
            RateLimitRule("/api/v1/listings", "read", settings.rate_limit_read_requests),
            RateLimitRule("/api/v1/availability", "read", settings.rate_limit_read_requests),
            RateLimitRule("/api/v1", "default", settings.rate_limit_default_requests),
        )
        self._hits: dict[tuple[str, str], deque[float]] = {}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self.enabled or request.method == "OPTIONS":
            return await call_next(request)

        rule = self._match_rule(request.url.path)
        if rule is None:
            return await call_next(request)

        client = self._client_key(request)
        key = (client, rule.bucket)
        now = time.monotonic()
        hits = self._hits.setdefault(key, deque())
        cutoff = now - self.window
        while hits and hits[0] <= cutoff:
            hits.popleft()

        if len(hits) >= rule.limit:
            retry_after = max(1, int(self.window - (now - hits[0])) + 1)
            return error_response(
                status_code=429,
                code=ErrorCode.RATE_LIMITED,
                message="Too many requests. Please retry shortly.",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(rule.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        hits.append(now)
        if len(self._hits) > self._MAX_TRACKED_CLIENTS:
            self._hits.pop(next(iter(self._hits)))
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(rule.limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, rule.limit - len(hits)))
        return response

    def _match_rule(self, path: str) -> RateLimitRule | None:
        for rule in self.rules:
            if path == rule.prefix or path.startswith(f"{rule.prefix}/"):
                return rule
        return None

    def _client_key(self, request: Request) -> str:
        if self.trust_proxy:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                candidate = forwarded.split(",", 1)[0].strip()
                if candidate:
                    return candidate
        return request.client.host if request.client else "unknown"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach defensive headers to API and health responses."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        super().__init__(app)
        self.is_https_deployment = settings.env in {Environment.STAGING, Environment.PRODUCTION}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        path = request.url.path
        if not (path.startswith("/api/") or path.startswith("/health/")):
            return response

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cache-Control", "no-store")
        if path.startswith("/api/"):
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
            )
        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
        if self.is_https_deployment and (
            request.url.scheme == "https" or forwarded_proto == "https"
        ):
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response
