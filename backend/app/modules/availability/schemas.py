"""Availability request and response schemas."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

MAX_AVAILABILITY_DAYS = 31
SLOT_MINUTES = 15


def _require_aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone offset")
    return value


def _require_grid(value: datetime, field: str) -> datetime:
    if value.minute % SLOT_MINUTES or value.second or value.microsecond:
        raise ValueError(f"{field} must be aligned to a 15-minute boundary")
    return value


def validate_window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """Validate a public availability window."""
    _require_aware(start, "from")
    _require_aware(end, "to")
    _require_grid(start, "from")
    _require_grid(end, "to")
    if end <= start:
        raise ValueError("to must be after from")
    if end - start > timedelta(days=MAX_AVAILABILITY_DAYS):
        raise ValueError("availability window cannot exceed 31 days")
    return start, end


class AvailabilityWindow(BaseModel):
    start: datetime
    end: datetime


class AvailabilityResponse(BaseModel):
    listing_id: UUID
    timezone: str
    from_: datetime = Field(serialization_alias="from")
    to: datetime
    windows: list[AvailabilityWindow]

    model_config = ConfigDict(populate_by_name=True)


class AvailabilityRuleRead(BaseModel):
    id: UUID
    weekday: int
    start_time: time
    end_time: time
    valid_from: date | None
    valid_to: date | None


class AvailabilityRuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekday: int = Field(ge=1, le=7)
    start_time: time
    end_time: time
    valid_from: date | None = None
    valid_to: date | None = None

    @model_validator(mode="after")
    def validate_rule(self) -> Self:
        if (
            self.start_time.minute % SLOT_MINUTES
            or self.start_time.second
            or self.start_time.microsecond
        ):
            raise ValueError("start_time must be aligned to a 15-minute boundary")
        if self.end_time.minute % SLOT_MINUTES or self.end_time.second or self.end_time.microsecond:
            raise ValueError("end_time must be aligned to a 15-minute boundary")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time; split overnight windows")
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_to < self.valid_from
        ):
            raise ValueError("valid_to must be on or after valid_from")
        return self

    def fingerprint(self) -> dict[str, object]:
        return {
            "weekday": self.weekday,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
        }


class AvailabilityRulesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rules: list[AvailabilityRuleInput] = Field(default_factory=list, max_length=50)


class BlockCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: datetime
    end: datetime
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("start", "end")
    @classmethod
    def validate_timestamp(cls, value: datetime, info: ValidationInfo) -> datetime:
        field = info.field_name or "timestamp"
        return _require_grid(_require_aware(value, field), field)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        if self.end - self.start > timedelta(days=MAX_AVAILABILITY_DAYS):
            raise ValueError("blocked interval cannot exceed 31 days")
        return self


class BlockRead(BaseModel):
    id: UUID
    start: datetime
    end: datetime
    reason: str | None
    created_at: datetime


class BlockCreateResponse(BlockRead):
    pass
