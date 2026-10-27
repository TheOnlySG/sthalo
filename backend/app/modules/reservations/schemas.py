"""Reservation request, quote, and response schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.listings.models import PricingModel, ReservationStatus
from app.modules.profiles.models import VehicleType

ViewerRole = Literal["customer", "owner", "admin"]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime values must include a timezone offset")
    return value.astimezone(UTC)


class ReservationWindowRequest(BaseModel):
    """Input shared by quote and hold creation."""

    model_config = ConfigDict(extra="forbid")

    listing_id: UUID
    vehicle_id: UUID
    start: datetime
    end: datetime

    @field_validator("start", "end")
    @classmethod
    def require_aware_datetime(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        for field_name, value in (("start", self.start), ("end", self.end)):
            if value.second or value.microsecond:
                raise ValueError(f"{field_name} must align to a whole minute")
            if value.minute % 15:
                raise ValueError(f"{field_name} must align to a 15-minute boundary")
        return self


class ReservationCreate(ReservationWindowRequest):
    """Create a pending-confirmation hold."""


class PriceBreakdown(BaseModel):
    pricing_model: PricingModel
    duration_minutes: int
    billable_minutes: int
    chargeable_days: int
    hourly_rate_paise: int | None
    daily_cap_paise: int | None
    hourly_component_paise: int
    cap_component_paise: int
    total_paise: int
    calculation: str


class ReservationQuote(BaseModel):
    listing_id: UUID
    start: datetime
    end: datetime
    currency: Literal["INR"] = "INR"
    base_amount_paise: int
    total_paise: int
    price: PriceBreakdown


class ReservationCancellation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ReservationListingRead(BaseModel):
    id: UUID
    title: str
    locality: str
    city: str
    latitude: float
    longitude: float


class ReservationVehicleRead(BaseModel):
    id: UUID
    vehicle_type: VehicleType
    registration_no: str | None
    length_mm: int | None
    width_mm: int | None
    height_mm: int | None
    is_ev: bool


class ReservationRead(BaseModel):
    id: UUID
    reference: str
    status: ReservationStatus
    viewer_role: ViewerRole
    listing: ReservationListingRead
    vehicle: ReservationVehicleRead
    customer_name: str | None = None
    owner_name: str
    start: datetime
    end: datetime
    hold_expires_at: datetime | None
    currency: Literal["INR"]
    base_amount_paise: int
    total_paise: int
    price_snapshot: dict[str, Any]
    can_confirm: bool
    can_cancel: bool
    exact_address: str | None = None
    pincode: str | None = None
    exact_latitude: float | None = None
    exact_longitude: float | None = None
    access_instructions: str | None = None
    cancel_reason: str | None = None
    confirmed_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    expired_at: datetime | None
    created_at: datetime
