"""Public availability and owner availability management endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.db.session import get_session
from app.modules.availability.schemas import (
    AvailabilityResponse,
    AvailabilityRuleRead,
    AvailabilityRulesPayload,
    BlockCreate,
    BlockRead,
    validate_window,
)
from app.modules.availability.service import (
    create_block,
    delete_block,
    get_public_availability,
    list_blocks,
    list_rules,
    replace_rules,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User

public_router = APIRouter(prefix="/parking-listings", tags=["availability"])
owner_router = APIRouter(prefix="/owner/parking-listings", tags=["owner availability"])


@public_router.get("/{listing_id}/availability", response_model=AvailabilityResponse)
async def get_listing_availability(
    listing_id: UUID,
    from_: Annotated[datetime, Query(alias="from")],
    to: Annotated[datetime, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AvailabilityResponse:
    try:
        start, end = validate_window(from_, to)
    except ValueError as exc:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            str(exc),
            status_code=422,
        ) from exc
    return await get_public_availability(session, listing_id, start, end)


@owner_router.get(
    "/{listing_id}/availability-rules",
    response_model=list[AvailabilityRuleRead],
)
async def get_availability_rules(
    listing_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[AvailabilityRuleRead]:
    return await list_rules(session, user, listing_id)


@owner_router.put(
    "/{listing_id}/availability-rules",
    response_model=list[AvailabilityRuleRead],
)
async def put_availability_rules(
    listing_id: UUID,
    payload: AvailabilityRulesPayload,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[AvailabilityRuleRead]:
    return await replace_rules(session, user, listing_id, payload)


@owner_router.get("/{listing_id}/blocks", response_model=list[BlockRead])
async def get_blocks(
    listing_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[BlockRead]:
    return await list_blocks(session, user, listing_id)


@owner_router.post(
    "/{listing_id}/blocks",
    response_model=BlockRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_block(
    listing_id: UUID,
    payload: BlockCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BlockRead:
    return await create_block(session, user, listing_id, payload)


@owner_router.delete(
    "/{listing_id}/blocks/{block_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_block(
    listing_id: UUID,
    block_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await delete_block(session, user, listing_id, block_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
