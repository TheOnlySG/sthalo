"""Local user profile model."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class User(Base):
    """Application profile mirrored from a Supabase Auth user.

    The database enforces the relationship to `auth.users`; the ORM deliberately
    does not model Supabase-managed tables.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "char_length(full_name) BETWEEN 2 AND 120",
            name="full_name_length",
        ),
        CheckConstraint("status IN ('active', 'suspended')", name="status"),
        CheckConstraint(
            "(owner_terms_version IS NULL) = (owner_terms_accepted_at IS NULL)",
            name="owner_terms_pair",
        ),
        {"schema": "sthalo"},
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=text("'active'"),
    )
    owner_terms_version: Mapped[str | None] = mapped_column(String(50))
    owner_terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
