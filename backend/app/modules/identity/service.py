"""Profile provisioning and owner-terms application logic."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.integrations.auth.verifier import TokenClaims
from app.modules.identity.models import User, UserStatus

CURRENT_OWNER_TERMS_VERSION = "2026-10-26"
_logger = structlog.get_logger("sthalo.identity")


def _fallback_email(claims: TokenClaims) -> str:
    return f"{claims.subject}@invalid.local"


def _default_full_name(claims: TokenClaims, email: str) -> str:
    candidate = claims.full_name or email.split("@", 1)[0] or "Sthalo user"
    normalized = " ".join(candidate.split())[:120]
    if len(normalized) < 2:
        return "Sthalo user"
    return normalized


def _reject_suspended(user: User) -> None:
    if user.status == UserStatus.SUSPENDED:
        raise AppError(
            ErrorCode.FORBIDDEN,
            "This account is suspended.",
            status_code=403,
        )


async def ensure_profile(session: AsyncSession, claims: TokenClaims) -> User:
    """Return the local profile, creating one defensively if the trigger missed."""
    user = await session.get(User, claims.subject)
    if user is not None:
        _reject_suspended(user)
        return user

    email = (claims.email or _fallback_email(claims)).strip().lower()
    full_name = _default_full_name(claims, email)
    statement = (
        insert(User)
        .values(
            id=claims.subject,
            email=email,
            full_name=full_name,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    await session.execute(statement)
    await session.commit()

    user = await session.get(User, claims.subject)
    if user is None:
        raise AppError(
            ErrorCode.UNAUTHENTICATED,
            "The local user profile could not be provisioned.",
            status_code=401,
        )
    _reject_suspended(user)
    _logger.info("user_profile_provisioned", user_id=str(user.id))
    return user


async def update_profile(
    session: AsyncSession,
    claims: TokenClaims,
    values: Mapping[str, Any],
) -> User:
    """Apply a validated partial profile update and return the fresh row."""
    user = await ensure_profile(session, claims)
    for field in ("full_name", "phone"):
        if field in values:
            setattr(user, field, values[field])

    if values:
        await session.commit()
        await session.refresh(user)
        _logger.info(
            "user_profile_updated",
            user_id=str(user.id),
            fields=sorted(values),
        )
    return user


async def accept_owner_terms(session: AsyncSession, claims: TokenClaims) -> User:
    """Record acceptance of the current owner terms version idempotently."""
    user = await ensure_profile(session, claims)
    if (
        user.owner_terms_version == CURRENT_OWNER_TERMS_VERSION
        and user.owner_terms_accepted_at is not None
    ):
        return user

    user.owner_terms_version = CURRENT_OWNER_TERMS_VERSION
    user.owner_terms_accepted_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(user)
    _logger.info(
        "owner_terms_accepted",
        user_id=str(user.id),
        version=CURRENT_OWNER_TERMS_VERSION,
    )
    return user
