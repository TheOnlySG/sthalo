"""Audit event recording helpers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.request_id import get_request_id
from app.modules.audit.models import AuditEvent
from app.modules.identity.models import User


def record_event(
    session: AsyncSession,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """Stage an audit event in the caller's transaction."""
    session.add(
        AuditEvent(
            actor_id=actor.id if actor else None,
            actor_type="system" if actor is None else ("admin" if actor.is_admin else "user"),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            ip=ip,
            request_id=get_request_id(),
        )
    )
