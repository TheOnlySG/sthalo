"""Reusable Supabase authentication and local authorization dependencies."""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.db.session import get_session
from app.integrations.auth.jwks import JwksCache, unauthenticated
from app.integrations.auth.verifier import (
    JWTVerifier,
    TokenClaims,
    TokenVerificationError,
)
from app.modules.identity.models import User, UserStatus

_logger = structlog.get_logger("sthalo.auth")
_bearer = HTTPBearer(auto_error=False, scheme_name="SupabaseAccessToken")


def get_jwks_cache(request: Request) -> JwksCache:
    """Return the process-wide JWKS cache, creating it lazily."""
    cache = getattr(request.app.state, "jwks_cache", None)
    if isinstance(cache, JwksCache):
        return cache

    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        raise RuntimeError("Application settings are not configured")
    cache = JwksCache(settings.supabase_jwks_url)
    request.app.state.jwks_cache = cache
    return cache


def get_token_verifier(
    request: Request,
    cache: Annotated[JwksCache, Depends(get_jwks_cache)],
) -> JWTVerifier:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        raise RuntimeError("Application settings are not configured")
    return JWTVerifier(settings, cache)


async def get_token_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    verifier: Annotated[JWTVerifier, Depends(get_token_verifier)],
) -> TokenClaims:
    """Verify the bearer token and return its trusted claims."""
    if credentials is None:
        raise unauthenticated()
    try:
        return await verifier.verify(credentials.credentials)
    except TokenVerificationError as exc:
        _logger.warning("access_token_rejected", reason=exc.reason)
        raise unauthenticated() from exc


async def get_current_user(
    claims: Annotated[TokenClaims, Depends(get_token_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Load the local profile and reject missing or suspended accounts."""
    user = await session.get(User, claims.subject)
    if user is None:
        raise unauthenticated("The local user profile does not exist.")
    if user.status == UserStatus.SUSPENDED:
        raise AppError(
            ErrorCode.FORBIDDEN,
            "This account is suspended.",
            status_code=403,
        )
    return user


async def get_admin_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require the local admin flag; token roles are never trusted."""
    if not user.is_admin:
        raise AppError(
            ErrorCode.FORBIDDEN,
            "Administrator access is required.",
            status_code=403,
        )
    return user


async def require_verified_email(
    claims: Annotated[TokenClaims, Depends(get_token_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenClaims:
    """Require the Supabase-managed auth record to have a confirmed email."""
    confirmed_at = await session.scalar(
        text("SELECT email_confirmed_at FROM auth.users WHERE id = :user_id"),
        {"user_id": claims.subject},
    )
    if confirmed_at is None:
        raise AppError(
            ErrorCode.FORBIDDEN,
            "Email verification is required.",
            status_code=403,
        )
    return claims
