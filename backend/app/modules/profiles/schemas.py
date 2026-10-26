"""Vehicle request and response schemas."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.profiles.models import VehicleType


def _normalize_registration(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", "", value.strip().upper())
    return normalized or None


class VehicleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehicle_type: VehicleType
    registration_no: str | None = Field(default=None, max_length=32)
    length_mm: int | None = Field(default=None, gt=0, le=10_000)
    width_mm: int | None = Field(default=None, gt=0, le=10_000)
    height_mm: int | None = Field(default=None, gt=0, le=10_000)
    is_ev: bool = False

    @field_validator("registration_no")
    @classmethod
    def normalize_registration_no(cls, value: str | None) -> str | None:
        return _normalize_registration(value)


class VehicleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehicle_type: VehicleType | None = None
    registration_no: str | None = Field(default=None, max_length=32)
    length_mm: int | None = Field(default=None, gt=0, le=10_000)
    width_mm: int | None = Field(default=None, gt=0, le=10_000)
    height_mm: int | None = Field(default=None, gt=0, le=10_000)
    is_ev: bool | None = None

    @field_validator("registration_no")
    @classmethod
    def normalize_registration_no(cls, value: str | None) -> str | None:
        return _normalize_registration(value)


class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vehicle_type: VehicleType
    registration_no: str | None
    length_mm: int | None
    width_mm: int | None
    height_mm: int | None
    is_ev: bool
    created_at: datetime
    updated_at: datetime
