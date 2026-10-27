"""Read-only administrator response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.modules.reservations.schemas import ReservationRead


class AdminOverview(BaseModel):
    pending_listings: int
    live_reservations: int
    expiring_holds: int


class AuditEventRead(BaseModel):
    id: UUID
    actor_id: UUID | None
    actor_type: str
    actor_name: str | None
    actor_email: str | None
    action: str
    entity_type: str
    entity_id: UUID | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    request_id: str | None
    created_at: datetime


class AdminReservationDetail(BaseModel):
    reservation: ReservationRead
    audit: list[AuditEventRead]
