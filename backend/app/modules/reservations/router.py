"""Customer and owner reservation endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.integrations.auth.verifier import TokenClaims
from app.modules.identity.dependencies import get_current_user, require_verified_email
from app.modules.identity.models import User
from app.modules.listings.models import ReservationStatus
from app.modules.reservations.schemas import (
    ReservationCancellation,
    ReservationCreate,
    ReservationQuote,
    ReservationRead,
    ReservationWindowRequest,
)
from app.modules.reservations.service import (
    cancel_reservation,
    confirm_reservation,
    create_reservation,
    get_reservation,
    list_customer_reservations,
    list_owner_reservations,
    quote_reservation,
)

router = APIRouter(prefix="/reservations", tags=["reservations"])
owner_router = APIRouter(prefix="/owner/reservations", tags=["owner reservations"])

IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key")]


@router.post("/quote", response_model=ReservationQuote)
async def post_quote(
    payload: ReservationWindowRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReservationQuote:
    return await quote_reservation(session, user, payload)


@router.post("", response_model=ReservationRead, status_code=status.HTTP_201_CREATED)
async def post_reservation(
    payload: ReservationCreate,
    idempotency_key: IdempotencyKey,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    _verified: Annotated[TokenClaims, Depends(require_verified_email)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReservationRead:
    reservation, response_status = await create_reservation(
        session,
        user,
        payload,
        idempotency_key,
    )
    response.status_code = response_status
    return reservation


@router.get("/me", response_model=list[ReservationRead])
async def get_my_reservations(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    reservation_status: Annotated[ReservationStatus | None, Query(alias="status")] = None,
) -> list[ReservationRead]:
    return await list_customer_reservations(session, user, reservation_status)


@owner_router.get("", response_model=list[ReservationRead])
async def get_owner_reservations(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    reservation_status: Annotated[ReservationStatus | None, Query(alias="status")] = None,
) -> list[ReservationRead]:
    return await list_owner_reservations(session, user, reservation_status)


@router.get("/{reservation_id}", response_model=ReservationRead)
async def get_reservation_detail(
    reservation_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReservationRead:
    return await get_reservation(session, user, reservation_id)


@router.post("/{reservation_id}/confirm", response_model=ReservationRead)
async def post_confirm(
    reservation_id: UUID,
    idempotency_key: IdempotencyKey,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReservationRead:
    reservation, _status = await confirm_reservation(
        session,
        user,
        reservation_id,
        idempotency_key,
    )
    return reservation


@router.post("/{reservation_id}/cancel", response_model=ReservationRead)
async def post_cancel(
    reservation_id: UUID,
    payload: ReservationCancellation,
    idempotency_key: IdempotencyKey,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReservationRead:
    reservation, _status = await cancel_reservation(
        session,
        user,
        reservation_id,
        payload.reason,
        idempotency_key,
    )
    return reservation
