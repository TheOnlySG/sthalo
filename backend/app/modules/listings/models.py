"""Parking listing, parking attributes, resource, and photo models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSTZRANGE
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.identity.models import User


class ListingStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    REJECTED = "rejected"
    PAUSED = "paused"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


LISTING_STATUS_VALUES = tuple(item.value for item in ListingStatus)


class ParkingType(StrEnum):
    DRIVEWAY = "driveway"
    GARAGE = "garage"
    SOCIETY_SLOT = "society_slot"
    OPEN_LOT = "open_lot"
    BASEMENT = "basement"
    SHOP_FRONTAGE = "shop_frontage"
    OTHER = "other"


class AccessMethod(StrEnum):
    OPEN = "open"
    GUARD_CHECKIN = "guard_checkin"
    CODE = "code"
    KEY_HANDOVER = "key_handover"
    REMOTE_OWNER = "remote_owner"


class PricingModel(StrEnum):
    HOURLY = "hourly"
    HOURLY_WITH_DAILY_CAP = "hourly_with_daily_cap"
    FLAT_DAILY = "flat_daily"


class Listing(Base):
    """A parking listing owned by a local user."""

    __tablename__ = "listings"
    __table_args__ = (
        CheckConstraint("kind = 'parking'", name="kind"),
        CheckConstraint("char_length(title) BETWEEN 5 AND 80", name="title_length"),
        CheckConstraint("char_length(description) <= 2000", name="description_length"),
        CheckConstraint(
            "char_length(address_line) BETWEEN 3 AND 240",
            name="address_length",
        ),
        CheckConstraint(
            "char_length(locality) BETWEEN 2 AND 120",
            name="locality_length",
        ),
        CheckConstraint("char_length(city) BETWEEN 2 AND 120", name="city_length"),
        CheckConstraint("char_length(state) BETWEEN 2 AND 120", name="state_length"),
        CheckConstraint("pincode ~ '^[0-9]{6}$'", name="pincode"),
        CheckConstraint(
            "status IN ("
            "'draft', 'pending_review', 'active', 'rejected', "
            "'paused', 'suspended', 'archived'"
            ")",
            name="status",
        ),
        CheckConstraint("verification_status IN ('unverified')", name="verification_status"),
        CheckConstraint("timezone = 'Asia/Kolkata'", name="timezone"),
        Index("ix_listings_owner_created", "owner_id", "created_at"),
        Index("ix_listings_status_kind", "status", "kind"),
        Index(
            "ix_listings_location_gist",
            "location",
            postgresql_using="gist",
        ),
        Index(
            "ix_listings_public_location_gist",
            "public_location",
            postgresql_using="gist",
        ),
        {"schema": "sthalo"},
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    owner_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sthalo.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'parking'"),
    )
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=False,
    )
    public_location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=False,
    )
    address_line: Mapped[str] = mapped_column(String(240), nullable=False)
    locality: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(120), nullable=False)
    pincode: Mapped[str] = mapped_column(String(6), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        server_default=text("'draft'"),
    )
    verification_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'unverified'"),
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default=text("'Asia/Kolkata'"),
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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

    owner: Mapped[User] = relationship(lazy="joined")
    parking: Mapped[ParkingListing | None] = relationship(
        back_populates="listing",
        uselist=False,
        cascade="all, delete-orphan",
    )
    resources: Mapped[list[Resource]] = relationship(
        back_populates="listing",
        cascade="all, delete-orphan",
    )
    photos: Mapped[list[ListingPhoto]] = relationship(
        back_populates="listing",
        cascade="all, delete-orphan",
        order_by="ListingPhoto.position",
    )


class ParkingListing(Base):
    """Parking-specific attributes for a listing."""

    __tablename__ = "parking_listings"
    __table_args__ = (
        CheckConstraint(
            "parking_type IN ("
            "'driveway', 'garage', 'society_slot', 'open_lot', "
            "'basement', 'shop_frontage', 'other'"
            ")",
            name="parking_type",
        ),
        CheckConstraint(
            "array_length(supported_vehicle_types, 1) >= 1 "
            "AND supported_vehicle_types <@ ARRAY["
            "'two_wheeler', 'hatchback', 'sedan', 'suv', 'large'"
            "]::text[]",
            name="supported_vehicle_types",
        ),
        CheckConstraint(
            "max_length_mm IS NULL OR max_length_mm > 0",
            name="max_length",
        ),
        CheckConstraint(
            "max_width_mm IS NULL OR max_width_mm > 0",
            name="max_width",
        ),
        CheckConstraint(
            "max_height_mm IS NULL OR max_height_mm > 0",
            name="max_height",
        ),
        CheckConstraint(
            "access_method IN ('open', 'guard_checkin', 'code', 'key_handover', 'remote_owner')",
            name="access_method",
        ),
        CheckConstraint(
            "access_instructions IS NULL OR char_length(access_instructions) <= 1000",
            name="access_instructions",
        ),
        CheckConstraint("cardinality(amenities) <= 20", name="amenities"),
        CheckConstraint("char_length(restrictions) <= 1000", name="restrictions"),
        CheckConstraint(
            "pricing_model IN ('hourly', 'hourly_with_daily_cap', 'flat_daily')",
            name="pricing_model",
        ),
        CheckConstraint(
            "price_hourly_paise IS NULL OR price_hourly_paise >= 0",
            name="hourly_price",
        ),
        CheckConstraint(
            "price_daily_cap_paise IS NULL OR price_daily_cap_paise >= 0",
            name="daily_price",
        ),
        CheckConstraint(
            "("
            "pricing_model = 'hourly' "
            "AND price_hourly_paise IS NOT NULL "
            "AND price_daily_cap_paise IS NULL"
            ") OR ("
            "pricing_model = 'hourly_with_daily_cap' "
            "AND price_hourly_paise IS NOT NULL "
            "AND price_daily_cap_paise IS NOT NULL "
            "AND price_daily_cap_paise >= price_hourly_paise"
            ") OR ("
            "pricing_model = 'flat_daily' "
            "AND price_hourly_paise IS NULL "
            "AND price_daily_cap_paise IS NOT NULL"
            ")",
            name="pricing_shape",
        ),
        CheckConstraint("min_booking_minutes >= 30", name="min_booking"),
        CheckConstraint(
            "max_booking_minutes >= min_booking_minutes AND max_booking_minutes <= 10080",
            name="max_booking",
        ),
        CheckConstraint(
            "advance_booking_max_days BETWEEN 1 AND 90",
            name="advance_days",
        ),
        {"schema": "sthalo"},
    )

    listing_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sthalo.listings.id", ondelete="CASCADE"),
        primary_key=True,
    )
    parking_type: Mapped[str] = mapped_column(String(24), nullable=False)
    supported_vehicle_types: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
    )
    max_length_mm: Mapped[int | None] = mapped_column(Integer)
    max_width_mm: Mapped[int | None] = mapped_column(Integer)
    max_height_mm: Mapped[int | None] = mapped_column(Integer)
    is_covered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    access_method: Mapped[str] = mapped_column(String(24), nullable=False)
    access_instructions: Mapped[str | None] = mapped_column(Text)
    amenities: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    restrictions: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''"),
    )
    pricing_model: Mapped[str] = mapped_column(String(32), nullable=False)
    price_hourly_paise: Mapped[int | None] = mapped_column(BigInteger)
    price_daily_cap_paise: Mapped[int | None] = mapped_column(BigInteger)
    min_booking_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("30"),
    )
    max_booking_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1440"),
    )
    advance_booking_max_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("30"),
    )

    listing: Mapped[Listing] = relationship(back_populates="parking")


class Resource(Base):
    """A bookable resource belonging to a listing."""

    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint("char_length(label) BETWEEN 1 AND 80", name="label"),
        Index("ix_resources_listing_id", "listing_id"),
        Index(
            "ux_resources_listing_main_bay",
            "listing_id",
            unique=True,
            postgresql_where=text("label = 'Main bay'"),
        ),
        {"schema": "sthalo"},
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    listing_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sthalo.listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        server_default=text("'Main bay'"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    listing: Mapped[Listing] = relationship(back_populates="resources")


class ListingPhoto(Base):
    """A re-encoded listing photo stored in the private bucket."""

    __tablename__ = "listing_photos"
    __table_args__ = (
        CheckConstraint(
            "mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="mime_type",
        ),
        CheckConstraint(
            "size_bytes > 0 AND size_bytes <= 5242880",
            name="size",
        ),
        CheckConstraint("width > 0 AND height > 0", name="dimensions"),
        CheckConstraint("position BETWEEN 0 AND 7", name="position"),
        Index("ix_listing_photos_listing_position", "listing_id", "position"),
        UniqueConstraint(
            "listing_id",
            "position",
            name="uq_listing_photos_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        Index(
            "ux_listing_photos_listing_cover",
            "listing_id",
            unique=True,
            postgresql_where=text("is_cover"),
        ),
        {"schema": "sthalo"},
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    listing_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sthalo.listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_cover: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    listing: Mapped[Listing] = relationship(back_populates="photos")


class ReservationStatus(StrEnum):
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Reservation(Base):
    """Reservation records needed by lifecycle safety checks.

    Booking APIs are added in a later phase; V2 keeps the core schema and
    constraints so archiving can never silently orphan a future booking.
    """

    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'pending_confirmation', 'confirmed', 'active', "
            "'completed', 'cancelled', 'expired'"
            ")",
            name="status",
        ),
        CheckConstraint("lower(time_range) < upper(time_range)", name="time_range"),
        CheckConstraint(
            "status <> 'pending_confirmation' OR hold_expires_at IS NOT NULL",
            name="hold_expiry",
        ),
        CheckConstraint("currency = 'INR'", name="currency"),
        CheckConstraint(
            "base_amount_paise >= 0 AND total_paise >= 0",
            name="amounts",
        ),
        CheckConstraint(
            "cancel_reason IS NULL OR char_length(cancel_reason) <= 500",
            name="cancel_reason",
        ),
        Index(
            "ix_reservations_hold_expiry",
            "hold_expires_at",
            postgresql_where=text("status = 'pending_confirmation'"),
        ),
        Index("ix_reservations_customer_created", "customer_id", "created_at"),
        Index("ix_reservations_owner_created", "owner_id", "created_at"),
        Index("ix_reservations_listing_status", "listing_id", "status"),
        Index("ix_reservations_resource_status", "resource_id", "status"),
        Index("ix_reservations_status_start", "status", text("lower(time_range)")),
        {"schema": "sthalo"},
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    reference: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    customer_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sthalo.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sthalo.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    listing_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sthalo.listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    resource_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sthalo.resources.id", ondelete="CASCADE"),
        nullable=False,
    )
    vehicle_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sthalo.vehicles.id", ondelete="CASCADE"),
        nullable=False,
    )
    time_range: Mapped[Any] = mapped_column(TSTZRANGE, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default=text("'INR'"),
    )
    base_amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    policy_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'phase1-demo-v1'"),
    )
    cancelled_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sthalo.users.id", ondelete="SET NULL"),
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
