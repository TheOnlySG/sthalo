"""Read-only administrator queries and audit timelines."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.schemas import AdminOverview, AuditEventRead
from app.modules.audit.models import AuditEvent
from app.modules.identity.models import User
from app.modules.listings.models import Listing, ListingStatus, Reservation, ReservationStatus

MAX_AUDIT_ROWS = 500


async def overview_counts(session: AsyncSession) -> AdminOverview:
    pending_listings = await session.scalar(
        select(func.count())
        .select_from(Listing)
        .where(Listing.status == ListingStatus.PENDING_REVIEW)
    )
    live_reservations = await session.scalar(
        select(func.count())
        .select_from(Reservation)
        .where(Reservation.status.in_((ReservationStatus.CONFIRMED, ReservationStatus.ACTIVE)))
    )
    expiring_holds = await session.scalar(
        select(func.count())
        .select_from(Reservation)
        .where(
            Reservation.status == ReservationStatus.PENDING_CONFIRMATION,
            Reservation.hold_expires_at > func.now(),
        )
    )
    return AdminOverview(
        pending_listings=int(pending_listings or 0),
        live_reservations=int(live_reservations or 0),
        expiring_holds=int(expiring_holds or 0),
    )


def _audit_read(
    event: AuditEvent,
    actor_name: str | None,
    actor_email: str | None,
) -> AuditEventRead:
    return AuditEventRead(
        id=event.id,
        actor_id=event.actor_id,
        actor_type=event.actor_type,
        actor_name=actor_name,
        actor_email=actor_email,
        action=event.action,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        before=event.before,
        after=event.after,
        request_id=event.request_id,
        created_at=event.created_at,
    )


async def list_audit_events(
    session: AsyncSession,
    *,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    actor_id: UUID | None = None,
    from_: datetime | None = None,
    to: datetime | None = None,
    limit: int = 100,
) -> list[AuditEventRead]:
    statement = (
        select(AuditEvent, User.full_name, User.email)
        .outerjoin(User, User.id == AuditEvent.actor_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(min(limit, MAX_AUDIT_ROWS))
    )
    if entity_type is not None:
        statement = statement.where(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        statement = statement.where(AuditEvent.entity_id == entity_id)
    if actor_id is not None:
        statement = statement.where(AuditEvent.actor_id == actor_id)
    if from_ is not None:
        statement = statement.where(AuditEvent.created_at >= from_)
    if to is not None:
        statement = statement.where(AuditEvent.created_at <= to)
    rows = (await session.execute(statement)).all()
    return [_audit_read(event, actor_name, actor_email) for event, actor_name, actor_email in rows]


async def reservation_audit(
    session: AsyncSession,
    reservation_id: UUID,
    *,
    limit: int = 100,
) -> list[AuditEventRead]:
    return await list_audit_events(
        session,
        entity_type="reservation",
        entity_id=reservation_id,
        limit=limit,
    )
