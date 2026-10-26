"""Discovery request parameters and privacy-safe search responses."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.listings.schemas import ParkingPublicRead
from app.modules.profiles.models import VehicleType

MAX_BBOX_SPAN_DEGREES = 0.5
MAX_BBOX_AREA_DEGREES = 0.25


class SearchSort(StrEnum):
    DISTANCE = "distance"
    PRICE = "price"


class SearchMode(StrEnum):
    RADIUS = "radius"
    BBOX = "bbox"


class ParkingSearchParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    radius_m: int | None = Field(default=None, ge=100, le=10_000)
    bbox: str | None = Field(default=None, max_length=80)
    vehicle_type: VehicleType | None = None
    max_price_paise: int | None = Field(default=None, ge=0, le=10_000_000)
    covered: bool | None = None
    sort: SearchSort = SearchSort.DISTANCE
    limit: int = Field(default=20, ge=1, le=50)
    cursor: str | None = Field(default=None, max_length=512)

    bbox_bounds: tuple[float, float, float, float] | None = Field(
        default=None,
        exclude=True,
    )

    @model_validator(mode="after")
    def validate_search_scope(self) -> Self:
        has_coordinates = self.latitude is not None or self.longitude is not None
        if self.bbox is not None:
            if has_coordinates or self.radius_m is not None:
                raise ValueError("bbox cannot be combined with lat, lng, or radius_m")
            parts = self.bbox.split(",")
            if len(parts) != 4:
                raise ValueError("bbox must be min_lng,min_lat,max_lng,max_lat")
            try:
                parsed: tuple[float, float, float, float] = (
                    float(parts[0]),
                    float(parts[1]),
                    float(parts[2]),
                    float(parts[3]),
                )
            except ValueError:
                raise ValueError("bbox must be min_lng,min_lat,max_lng,max_lat") from None
            min_lng, min_lat, max_lng, max_lat = parsed
            if not (-180 <= min_lng < max_lng <= 180):
                raise ValueError("bbox longitude values are invalid")
            if not (-90 <= min_lat < max_lat <= 90):
                raise ValueError("bbox latitude values are invalid")
            width = max_lng - min_lng
            height = max_lat - min_lat
            if (
                width > MAX_BBOX_SPAN_DEGREES
                or height > MAX_BBOX_SPAN_DEGREES
                or width * height > MAX_BBOX_AREA_DEGREES
            ):
                raise ValueError(
                    "bbox is too large; zoom in to an area at most 0.5 degrees wide and tall"
                )
            self.bbox_bounds = parsed
            return self

        if self.latitude is None or self.longitude is None:
            raise ValueError("Provide lat and lng, or bbox")
        return self

    @property
    def mode(self) -> SearchMode:
        return SearchMode.BBOX if self.bbox_bounds is not None else SearchMode.RADIUS

    @property
    def effective_radius_m(self) -> int:
        return self.radius_m or 2_000

    @property
    def center(self) -> tuple[float, float]:
        if self.bbox_bounds is not None:
            min_lng, min_lat, max_lng, max_lat = self.bbox_bounds
            return (
                (min_lat + max_lat) / 2,
                (min_lng + max_lng) / 2,
            )
        if self.latitude is None or self.longitude is None:
            raise RuntimeError("search center is missing")
        return self.latitude, self.longitude


class SearchListingItem(BaseModel):
    id: UUID
    title: str
    description: str
    latitude: float
    longitude: float
    locality: str
    city: str
    state: str
    parking: ParkingPublicRead
    cover_url: str | None
    distance_m: float
    updated_at: datetime


class ParkingSearchResponse(BaseModel):
    items: list[SearchListingItem]
    next_cursor: str | None
    mode: SearchMode
    center_latitude: float
    center_longitude: float
    radius_m: int | None
    bbox: list[float] | None
    sort: SearchSort
