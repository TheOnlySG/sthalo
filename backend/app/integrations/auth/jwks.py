"""Async JWKS fetching and key caching for Supabase access tokens."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import httpx
import jwt
import structlog

from app.core.errors import AppError, ErrorCode

SUPPORTED_ALGORITHMS = frozenset({"ES256", "RS256"})
_JWKS_TIMEOUT_SECONDS = 5.0
_logger = structlog.get_logger("sthalo.auth.jwks")

JwksFetcher = Callable[[], Awaitable[Mapping[str, Any]]]


class JwksError(Exception):
    """Raised when the signing-key set is unavailable or invalid."""


def _parse_keys(payload: Mapping[str, Any]) -> dict[str, jwt.PyJWK]:
    raw_keys = payload.get("keys")
    if not isinstance(raw_keys, list):
        raise JwksError("JWKS response does not contain a keys list")

    parsed: dict[str, jwt.PyJWK] = {}
    for raw in raw_keys:
        if not isinstance(raw, dict):
            continue
        kid = raw.get("kid")
        algorithm = raw.get("alg")
        use = raw.get("use")
        if not isinstance(kid, str) or not kid:
            continue
        if not isinstance(algorithm, str) or algorithm not in SUPPORTED_ALGORITHMS:
            continue
        if use not in (None, "sig"):
            continue
        try:
            parsed[kid] = jwt.PyJWK(raw, algorithm=algorithm)
        except (jwt.PyJWTError, ValueError, TypeError):
            _logger.warning("jwks_key_skipped", kid=kid, algorithm=algorithm)
    if not parsed:
        raise JwksError("JWKS response does not contain a supported signing key")
    return parsed


class JwksCache:
    """Fetch signing keys lazily and cache them for a bounded period."""

    def __init__(
        self,
        url: str,
        *,
        ttl_seconds: int = 300,
        fetch: JwksFetcher | None = None,
    ) -> None:
        self._url = url
        self._ttl_seconds = ttl_seconds
        self._fetch = fetch or self._fetch_http
        self._keys: dict[str, jwt.PyJWK] = {}
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def _fetch_http(self) -> Mapping[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=_JWKS_TIMEOUT_SECONDS) as client:
                response = await client.get(self._url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise JwksError("Could not fetch the Supabase signing keys") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise JwksError("Supabase signing keys are not valid JSON") from exc
        if not isinstance(payload, Mapping):
            raise JwksError("Supabase signing keys are not a JSON object")
        return payload

    async def _refresh(self) -> None:
        payload = await self._fetch()
        self._keys = _parse_keys(payload)
        self._expires_at = time.monotonic() + self._ttl_seconds
        _logger.info("jwks_refreshed", key_count=len(self._keys))

    async def get(self, kid: str) -> jwt.PyJWK:
        """Return the key for `kid`, refreshing the cache when needed."""
        if not kid:
            raise JwksError("Token header is missing a key ID")

        now = time.monotonic()
        if now < self._expires_at and kid in self._keys:
            return self._keys[kid]

        async with self._lock:
            now = time.monotonic()
            if now >= self._expires_at or kid not in self._keys:
                await self._refresh()
            key = self._keys.get(kid)
            if key is None:
                raise JwksError("Token key ID does not match a signing key")
            return key


def unauthenticated(message: str = "A valid access token is required.") -> AppError:
    """Return the standard 401 error used by auth dependencies."""
    return AppError(
        ErrorCode.UNAUTHENTICATED,
        message,
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
    )
