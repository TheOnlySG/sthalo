"""Reservation support models local to the booking module."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IdempotencyKey(Base):
    """A stored successful response for a customer-supplied idempotency key."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        CheckConstraint("char_length(key) BETWEEN 1 AND 128", name="key_length"),
        CheckConstraint(
            "(response_status IS NULL AND response_body IS NULL) "
            "OR (response_status IS NOT NULL AND response_body IS NOT NULL)",
            name="response_pair",
        ),
        UniqueConstraint("user_id", "key", name="uq_idempotency_user_key"),
        Index("ix_idempotency_keys_expires_at", "expires_at"),
        {"schema": "sthalo"},
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sthalo.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
