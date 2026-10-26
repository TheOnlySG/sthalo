"""Vehicle models owned by a local user profile."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VehicleType(StrEnum):
    TWO_WHEELER = "two_wheeler"
    HATCHBACK = "hatchback"
    SEDAN = "sedan"
    SUV = "suv"
    LARGE = "large"


VEHICLE_TYPE_VALUES = tuple(item.value for item in VehicleType)


class Vehicle(Base):
    """A customer vehicle used for fit checks and reservation records."""

    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint(
            "vehicle_type IN ('two_wheeler', 'hatchback', 'sedan', 'suv', 'large')",
            name="vehicle_type",
        ),
        CheckConstraint(
            "length_mm IS NULL OR length_mm > 0",
            name="length_positive",
        ),
        CheckConstraint(
            "width_mm IS NULL OR width_mm > 0",
            name="width_positive",
        ),
        CheckConstraint(
            "height_mm IS NULL OR height_mm > 0",
            name="height_positive",
        ),
        Index("ix_vehicles_user_id", "user_id"),
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
    vehicle_type: Mapped[str] = mapped_column(String(20), nullable=False)
    registration_no: Mapped[str | None] = mapped_column(String(32))
    length_mm: Mapped[int | None] = mapped_column(Integer)
    width_mm: Mapped[int | None] = mapped_column(Integer)
    height_mm: Mapped[int | None] = mapped_column(Integer)
    is_ev: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
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
