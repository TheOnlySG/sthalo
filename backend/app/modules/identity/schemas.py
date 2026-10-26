"""Profile request and response schemas."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.modules.identity.models import UserStatus

_PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{6,14}$")


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    phone: str | None
    is_admin: bool
    status: UserStatus
    owner_terms_version: str | None
    owner_terms_accepted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = None
    phone: str | None = None

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not 2 <= len(normalized) <= 120:
            raise ValueError("full_name must be between 2 and 120 characters")
        return normalized

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = re.sub(r"[\s()-]", "", value)
        if not normalized:
            return None
        if not _PHONE_PATTERN.fullmatch(normalized):
            raise ValueError("phone must be an E.164-like number with 7 to 15 digits")
        return normalized
