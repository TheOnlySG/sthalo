"""Read-only admin overview, reservation, and audit endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.db.session import get_session
from app.modules.admin.schemas import AdminOverview, AdminReservationDetail, AuditEventRead
from app.modules.admin.service import list_audit_events, overview_counts, reservation_audit
from app.modules.identity.dependencies import get_admin_user
from app.modules.identity.models import User
from app.modules.listings.models import ReservationStatus
from app.modules.reservations.schemas import ReservationRead
from app.modules.reservations.service import get_reservation, list_admin_reservations

router = APIRouter(prefix="/admin", tags=["admin"])


def _aware(value: datetime | None, field: str) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Request validation failed.",
            status_code=422,
            details=[
                {
                    "field": field,
                    "message": "Datetime filters must include a timezone offset.",
                    "type": "value_error",
                }
            ],
        )
    return value


@router.get("/overview", response_model=AdminOverview)
async def get_overview(
    _admin: Annotated[User, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AdminOverview:
    return await overview_counts(session)


@router.get("/reservations", response_model=list[ReservationRead])
async def get_admin_reservations(
    admin: Annotated[User, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    reservation_status: Annotated[ReservationStatus | None, Query(alias="status")] = None,
    listing_id: UUID | None = None,
) -> list[ReservationRead]:
    return await list_admin_reservations(
        session,
        admin,
        status=reservation_status,
        listing_id=listing_id,
    )


@router.get("/reservations/{reservation_id}", response_model=AdminReservationDetail)
async def get_admin_reservation(
    reservation_id: UUID,
    admin: Annotated[User, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AdminReservationDetail:
    reservation = await get_reservation(session, admin, reservation_id)
    audit = await reservation_audit(session, reservation_id)
    return AdminReservationDetail(reservation=reservation, audit=audit)


@router.get("/audit", response_model=list[AuditEventRead])
async def get_admin_audit(
    _admin: Annotated[User, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    actor_id: UUID | None = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AuditEventRead]:
    return await list_audit_events(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        from_=_aware(from_, "from"),
        to=_aware(to, "to"),
        limit=limit,
    )
