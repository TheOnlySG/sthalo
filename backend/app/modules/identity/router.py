"""Current-user profile and owner-terms endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.db.session import get_session
from app.integrations.auth.verifier import TokenClaims
from app.modules.identity.dependencies import get_token_claims
from app.modules.identity.schemas import ProfileUpdate, UserProfile
from app.modules.identity.service import (
    accept_owner_terms,
    ensure_profile,
    update_profile,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserProfile)
async def get_me(
    claims: Annotated[TokenClaims, Depends(get_token_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserProfile:
    """Return the current profile, provisioning it if the auth trigger missed."""
    user = await ensure_profile(session, claims)
    return UserProfile.model_validate(user)


@router.patch("/me", response_model=UserProfile)
async def patch_me(
    payload: ProfileUpdate,
    claims: Annotated[TokenClaims, Depends(get_token_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserProfile:
    """Update the caller's display name and/or phone number."""
    values = payload.model_dump(exclude_unset=True)
    if "full_name" in values and values["full_name"] is None:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Request validation failed.",
            status_code=422,
            details=[
                {
                    "field": "full_name",
                    "message": "full_name cannot be null",
                    "type": "value_error",
                }
            ],
        )
    user = await update_profile(session, claims, values)
    return UserProfile.model_validate(user)


@router.post("/me/accept-owner-terms", response_model=UserProfile)
async def accept_terms(
    claims: Annotated[TokenClaims, Depends(get_token_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserProfile:
    """Record acceptance of the current owner terms version."""
    user = await accept_owner_terms(session, claims)
    return UserProfile.model_validate(user)
