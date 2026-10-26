"""Public discovery endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.integrations.storage.dependencies import get_photo_storage
from app.integrations.storage.supabase import PhotoStorage
from app.modules.discovery.schemas import (
    ParkingSearchParams,
    ParkingSearchResponse,
    SearchSort,
)
from app.modules.discovery.service import search_parking_listings
from app.modules.profiles.models import VehicleType

router = APIRouter(prefix="/search", tags=["discovery"])


@router.get("/parking", response_model=ParkingSearchResponse)
async def search_parking(
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    radius_m: Annotated[int | None, Query(ge=100, le=10_000)] = None,
    bbox: Annotated[str | None, Query(max_length=80)] = None,
    vehicle_type: Annotated[VehicleType | None, Query()] = None,
    max_price_paise: Annotated[int | None, Query(ge=0, le=10_000_000)] = None,
    covered: Annotated[bool | None, Query()] = None,
    sort: Annotated[SearchSort, Query()] = SearchSort.DISTANCE,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
) -> ParkingSearchResponse:
    try:
        params = ParkingSearchParams(
            latitude=lat,
            longitude=lng,
            radius_m=radius_m,
            bbox=bbox,
            vehicle_type=vehicle_type,
            max_price_paise=max_price_paise,
            covered=covered,
            sort=sort,
            limit=limit,
            cursor=cursor,
            start=start,
            end=end,
        )
    except ValidationError as exc:
        errors = []
        for error in exc.errors():
            normalized = dict(error)
            normalized["loc"] = ("query", *error.get("loc", ()))
            errors.append(normalized)
        raise RequestValidationError(errors) from exc
    return await search_parking_listings(session, params, storage)
