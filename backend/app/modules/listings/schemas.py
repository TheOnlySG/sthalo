"""Listing request and response schemas."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.modules.listings.models import AccessMethod, ListingStatus, ParkingType, PricingModel
from app.modules.profiles.models import VehicleType

PINCODE_PATTERN = re.compile(r"^[0-9]{6}$")


def _strip(value: str) -> str:
    return value.strip()


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class ParkingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parking_type: ParkingType
    supported_vehicle_types: list[VehicleType] = Field(min_length=1, max_length=5)
    max_length_mm: int | None = Field(default=None, gt=0, le=10_000)
    max_width_mm: int | None = Field(default=None, gt=0, le=10_000)
    max_height_mm: int | None = Field(default=None, gt=0, le=10_000)
    is_covered: bool = False
    access_method: AccessMethod
    access_instructions: str | None = Field(default=None, max_length=1000)
    amenities: list[str] = Field(default_factory=list, max_length=20)
    restrictions: str = Field(default="", max_length=1000)
    pricing_model: PricingModel
    price_hourly_paise: int | None = Field(default=None, ge=0, le=10_000_000)
    price_daily_cap_paise: int | None = Field(default=None, ge=0, le=10_000_000)
    min_booking_minutes: int = Field(default=30, ge=30, le=10_080)
    max_booking_minutes: int = Field(default=1440, ge=30, le=10_080)
    advance_booking_max_days: int = Field(default=30, ge=1, le=90)

    @field_validator("supported_vehicle_types")
    @classmethod
    def unique_vehicle_types(cls, value: list[VehicleType]) -> list[VehicleType]:
        return list(dict.fromkeys(value))

    @field_validator("access_instructions")
    @classmethod
    def normalize_access_instructions(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("amenities")
    @classmethod
    def normalize_amenities(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if any(len(item) > 50 for item in normalized):
            raise ValueError("Amenity names must be at most 50 characters.")
        return list(dict.fromkeys(normalized))

    @field_validator("restrictions")
    @classmethod
    def normalize_restrictions(cls, value: str) -> str:
        return _strip(value)

    @model_validator(mode="after")
    def validate_booking_and_pricing(self) -> Self:
        if self.max_booking_minutes < self.min_booking_minutes:
            raise ValueError("max_booking_minutes must be at least min_booking_minutes")
        if self.pricing_model == PricingModel.HOURLY:
            if self.price_hourly_paise is None or self.price_daily_cap_paise is not None:
                raise ValueError("Hourly pricing requires only price_hourly_paise")
        elif self.pricing_model == PricingModel.HOURLY_WITH_DAILY_CAP:
            if self.price_hourly_paise is None or self.price_daily_cap_paise is None:
                raise ValueError("Hourly-with-cap pricing requires both prices")
            if self.price_daily_cap_paise < self.price_hourly_paise:
                raise ValueError("Daily cap cannot be lower than the hourly price")
        elif self.price_hourly_paise is not None or self.price_daily_cap_paise is None:
            raise ValueError("Flat-daily pricing requires only price_daily_cap_paise")
        return self


class ParkingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parking_type: ParkingType | None = None
    supported_vehicle_types: list[VehicleType] | None = Field(
        default=None, min_length=1, max_length=5
    )
    max_length_mm: int | None = Field(default=None, gt=0, le=10_000)
    max_width_mm: int | None = Field(default=None, gt=0, le=10_000)
    max_height_mm: int | None = Field(default=None, gt=0, le=10_000)
    is_covered: bool | None = None
    access_method: AccessMethod | None = None
    access_instructions: str | None = Field(default=None, max_length=1000)
    amenities: list[str] | None = Field(default=None, max_length=20)
    restrictions: str | None = Field(default=None, max_length=1000)
    pricing_model: PricingModel | None = None
    price_hourly_paise: int | None = Field(default=None, ge=0, le=10_000_000)
    price_daily_cap_paise: int | None = Field(default=None, ge=0, le=10_000_000)
    min_booking_minutes: int | None = Field(default=None, ge=30, le=10_080)
    max_booking_minutes: int | None = Field(default=None, ge=30, le=10_080)
    advance_booking_max_days: int | None = Field(default=None, ge=1, le=90)

    @field_validator("supported_vehicle_types")
    @classmethod
    def unique_vehicle_types(cls, value: list[VehicleType] | None) -> list[VehicleType] | None:
        if value is None:
            return None
        return list(dict.fromkeys(value))

    @field_validator("access_instructions")
    @classmethod
    def normalize_access_instructions(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("amenities")
    @classmethod
    def normalize_amenities(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [item.strip() for item in value if item.strip()]
        if any(len(item) > 50 for item in normalized):
            raise ValueError("Amenity names must be at most 50 characters.")
        return list(dict.fromkeys(normalized))

    @field_validator("restrictions")
    @classmethod
    def normalize_restrictions(cls, value: str | None) -> str | None:
        return _strip(value) if value is not None else None


class ListingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=5, max_length=80)
    description: str = Field(min_length=20, max_length=2000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address_line: str = Field(min_length=3, max_length=240)
    locality: str = Field(min_length=2, max_length=120)
    city: str = Field(min_length=2, max_length=120)
    state: str = Field(min_length=2, max_length=120)
    pincode: str
    owner_terms_accepted: bool
    parking: ParkingCreate

    @field_validator("title", "description", "address_line", "locality", "city", "state")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("pincode")
    @classmethod
    def validate_pincode(cls, value: str) -> str:
        cleaned = value.strip()
        if not PINCODE_PATTERN.fullmatch(cleaned):
            raise ValueError("Pincode must be exactly six digits")
        return cleaned


class ListingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=5, max_length=80)
    description: str | None = Field(default=None, min_length=20, max_length=2000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    address_line: str | None = Field(default=None, min_length=3, max_length=240)
    locality: str | None = Field(default=None, min_length=2, max_length=120)
    city: str | None = Field(default=None, min_length=2, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=120)
    pincode: str | None = None
    parking: ParkingUpdate | None = None

    @field_validator("title", "description", "address_line", "locality", "city", "state")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return _strip(value) if value is not None else None

    @field_validator("pincode")
    @classmethod
    def validate_pincode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not PINCODE_PATTERN.fullmatch(cleaned):
            raise ValueError("Pincode must be exactly six digits")
        return cleaned

    @model_validator(mode="after")
    def validate_coordinate_pair(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be updated together")
        return self


class ListingSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    declaration_accepted: bool


class ModerationAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, min_length=3, max_length=500)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class PhotoPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int | None = Field(default=None, ge=0, le=7)
    is_cover: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if self.position is None and self.is_cover is None:
            raise ValueError("Provide position or is_cover")
        return self


class PhotoRead(BaseModel):
    id: UUID
    url: str
    width: int
    height: int
    position: int
    is_cover: bool
    mime_type: str


class ParkingPublicRead(BaseModel):
    parking_type: ParkingType
    supported_vehicle_types: list[VehicleType]
    max_length_mm: int | None
    max_width_mm: int | None
    max_height_mm: int | None
    is_covered: bool
    access_method: AccessMethod
    amenities: list[str]
    restrictions: str
    pricing_model: PricingModel
    price_hourly_paise: int | None
    price_daily_cap_paise: int | None
    min_booking_minutes: int
    max_booking_minutes: int
    advance_booking_max_days: int


class ParkingOwnerRead(ParkingPublicRead):
    access_instructions: str | None


class ListingOwnerSummary(BaseModel):
    id: UUID
    title: str
    status: ListingStatus
    city: str
    locality: str
    cover_url: str | None
    photo_count: int
    updated_at: datetime
    moderation_note: str | None


class ListingOwnerRead(BaseModel):
    id: UUID
    title: str
    description: str
    status: ListingStatus
    latitude: float
    longitude: float
    address_line: str
    locality: str
    city: str
    state: str
    pincode: str
    parking: ParkingOwnerRead
    photos: list[PhotoRead]
    moderation_note: str | None
    submitted_at: datetime | None
    approved_at: datetime | None
    rejected_at: datetime | None
    paused_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ListingPublicRead(BaseModel):
    id: UUID
    title: str
    description: str
    latitude: float
    longitude: float
    locality: str
    city: str
    state: str
    parking: ParkingPublicRead
    photos: list[PhotoRead]
    updated_at: datetime


class AdminOwnerRead(BaseModel):
    id: UUID
    email: str
    full_name: str


class ListingAdminRead(ListingOwnerRead):
    owner: AdminOwnerRead
