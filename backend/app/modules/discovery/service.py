"""PostGIS discovery search over privacy-safe public listing locations."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import math
from dataclasses import dataclass
from typing import Any
from typing import cast as type_cast
from uuid import UUID

from geoalchemy2 import Geography, Geometry
from sqlalchemy import and_, cast, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload, selectinload

from app.core.errors import AppError, ErrorCode
from app.integrations.storage.supabase import PhotoStorage, PhotoStorageError
from app.modules.availability.service import available_listing_ids
from app.modules.discovery.schemas import (
    ParkingSearchParams,
    ParkingSearchResponse,
    SearchListingItem,
    SearchMode,
    SearchSort,
)
from app.modules.listings.models import Listing, ListingStatus, ParkingListing
from app.modules.listings.schemas import ParkingPublicRead

CURSOR_VERSION = 1

SearchRow = tuple[UUID, float, int, float, float]


@dataclass(frozen=True, slots=True)
class SearchCursor:
    sort: SearchSort
    value: float | int
    listing_id: UUID


async def search_parking_listings(
    session: AsyncSession,
    params: ParkingSearchParams,
    storage: PhotoStorage,
) -> ParkingSearchResponse:
    center_latitude, center_longitude = params.center
    center = cast(
        func.ST_SetSRID(
            func.ST_MakePoint(center_longitude, center_latitude),
            4326,
        ),
        Geography,
    )
    distance = func.ST_Distance(Listing.public_location, center)
    parking_price = func.coalesce(
        ParkingListing.price_hourly_paise,
        ParkingListing.price_daily_cap_paise,
    )

    parking_attrs_query = select(parking_price.label("effective_price_paise")).where(
        ParkingListing.listing_id == Listing.id
    )
    if params.vehicle_type is not None:
        parking_attrs_query = parking_attrs_query.where(
            ParkingListing.supported_vehicle_types.contains([params.vehicle_type.value])
        )
    if params.max_price_paise is not None:
        parking_attrs_query = parking_attrs_query.where(parking_price <= params.max_price_paise)
    if params.covered is not None:
        parking_attrs_query = parking_attrs_query.where(
            ParkingListing.is_covered.is_(params.covered)
        )
    parking_attrs = parking_attrs_query.limit(1).lateral("parking_attrs")
    price = parking_attrs.c.effective_price_paise

    statement = (
        select(
            Listing.id,
            distance.label("distance_m"),
            price.label("effective_price_paise"),
            func.ST_Y(cast(Listing.public_location, Geometry)).label("public_latitude"),
            func.ST_X(cast(Listing.public_location, Geometry)).label("public_longitude"),
        )
        .select_from(Listing)
        .join(parking_attrs, true())
        .where(Listing.status == ListingStatus.ACTIVE)
    )

    if params.bbox_bounds is not None:
        min_lng, min_lat, max_lng, max_lat = params.bbox_bounds
        statement = statement.where(
            func.ST_Intersects(
                cast(Listing.public_location, Geometry),
                func.ST_MakeEnvelope(min_lng, min_lat, max_lng, max_lat, 4326),
            )
        )
    else:
        statement = statement.where(
            func.ST_DWithin(
                Listing.public_location,
                center,
                params.effective_radius_m,
            )
        )

    availability_window = params.availability_window
    if params.cursor is not None and availability_window is None:
        cursor = _decode_cursor(params.cursor, params.sort)
        if params.sort == SearchSort.DISTANCE:
            statement = statement.where(
                or_(
                    distance > cursor.value,
                    and_(distance == cursor.value, Listing.id > cursor.listing_id),
                )
            )
        else:
            statement = statement.where(
                or_(
                    price > cursor.value,
                    and_(price == cursor.value, Listing.id > cursor.listing_id),
                )
            )

    if params.sort == SearchSort.DISTANCE:
        statement = statement.order_by(distance.asc(), Listing.id.asc())
    else:
        statement = statement.order_by(price.asc(), Listing.id.asc())

    if availability_window is None:
        statement = statement.limit(params.limit + 1)
    raw_rows = list(await session.execute(statement))
    rows: list[SearchRow] = [
        (
            type_cast(UUID, row[0]),
            type_cast(float, row[1]),
            type_cast(int, row[2]),
            type_cast(float, row[3]),
            type_cast(float, row[4]),
        )
        for row in raw_rows
    ]
    if availability_window is not None:
        if params.cursor is not None:
            cursor = _decode_cursor(params.cursor, params.sort)
            rows = [row for row in rows if _after_cursor(row, params.sort, cursor)]
        available = await available_listing_ids(
            session,
            [row[0] for row in rows],
            *availability_window,
        )
        rows = [row for row in rows if row[0] in available]
    page = rows[: params.limit]
    next_cursor = None
    if len(rows) > params.limit and page:
        last_listing_id, last_distance, last_price, _, _ = page[-1]
        last_value: float | int = (
            float(last_distance) if params.sort == SearchSort.DISTANCE else int(last_price)
        )
        next_cursor = _encode_cursor(params.sort, last_value, last_listing_id)

    page_ids = [row[0] for row in page]
    listings_by_id: dict[UUID, Listing] = {}
    if page_ids:
        listing_result = await session.execute(
            select(Listing)
            .where(Listing.id.in_(page_ids))
            .options(
                selectinload(Listing.parking),
                selectinload(Listing.photos),
                lazyload(Listing.owner),
            )
        )
        listings_by_id = {listing.id: listing for listing in listing_result.scalars()}
    page_listings = [listings_by_id[row[0]] for row in page]

    cover_urls = await asyncio.gather(*[_cover_url(listing, storage) for listing in page_listings])
    items = [
        _search_item(listing, float(distance_m), public_lat, public_lng, cover_url)
        for (_, distance_m, _, public_lat, public_lng), listing, cover_url in zip(
            page,
            page_listings,
            cover_urls,
            strict=True,
        )
    ]
    return ParkingSearchResponse(
        items=items,
        next_cursor=next_cursor,
        mode=params.mode,
        center_latitude=center_latitude,
        center_longitude=center_longitude,
        radius_m=params.effective_radius_m if params.mode == SearchMode.RADIUS else None,
        bbox=list(params.bbox_bounds) if params.bbox_bounds is not None else None,
        sort=params.sort,
    )


def _after_cursor(
    row: SearchRow,
    sort: SearchSort,
    cursor: SearchCursor,
) -> bool:
    value: float | int = float(row[1]) if sort == SearchSort.DISTANCE else int(row[2])
    return value > cursor.value or (value == cursor.value and row[0] > cursor.listing_id)


def _search_item(
    listing: Listing,
    distance_m: float,
    public_latitude: float,
    public_longitude: float,
    cover_url: str | None,
) -> SearchListingItem:
    if listing.parking is None:
        raise RuntimeError("Listing parking attributes are missing")
    parking = ParkingPublicRead.model_validate(
        {
            "parking_type": listing.parking.parking_type,
            "supported_vehicle_types": listing.parking.supported_vehicle_types,
            "max_length_mm": listing.parking.max_length_mm,
            "max_width_mm": listing.parking.max_width_mm,
            "max_height_mm": listing.parking.max_height_mm,
            "is_covered": listing.parking.is_covered,
            "access_method": listing.parking.access_method,
            "amenities": listing.parking.amenities,
            "restrictions": listing.parking.restrictions,
            "pricing_model": listing.parking.pricing_model,
            "price_hourly_paise": listing.parking.price_hourly_paise,
            "price_daily_cap_paise": listing.parking.price_daily_cap_paise,
            "min_booking_minutes": listing.parking.min_booking_minutes,
            "max_booking_minutes": listing.parking.max_booking_minutes,
            "advance_booking_max_days": listing.parking.advance_booking_max_days,
        }
    )
    return SearchListingItem(
        id=listing.id,
        title=listing.title,
        description=listing.description,
        latitude=public_latitude,
        longitude=public_longitude,
        locality=listing.locality,
        city=listing.city,
        state=listing.state,
        parking=parking,
        cover_url=cover_url,
        distance_m=round(max(distance_m, 0.0), 1),
        updated_at=listing.updated_at,
    )


async def _cover_url(listing: Listing, storage: PhotoStorage) -> str | None:
    cover = next((photo for photo in listing.photos if photo.is_cover), None)
    if cover is None:
        cover = next(iter(sorted(listing.photos, key=lambda item: item.position)), None)
    if cover is None:
        return None
    try:
        return await storage.signed_url(cover.storage_key)
    except PhotoStorageError as exc:
        raise AppError(
            ErrorCode.INTERNAL_ERROR,
            "Photo storage is unavailable.",
            status_code=500,
        ) from exc


def _encode_cursor(sort: SearchSort, value: float | int, listing_id: UUID) -> str:
    payload = json.dumps(
        {
            "v": CURSOR_VERSION,
            "sort": sort.value,
            "value": value,
            "id": str(listing_id),
        },
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(cursor: str, expected_sort: SearchSort) -> SearchCursor:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        if not isinstance(payload, dict) or payload.get("v") != CURSOR_VERSION:
            raise ValueError
        if payload.get("sort") != expected_sort.value:
            raise ValueError
        listing_id = UUID(str(payload["id"]))
        raw_value: Any = payload["value"]
        if expected_sort == SearchSort.DISTANCE:
            value = float(raw_value)
            if not math.isfinite(value):
                raise ValueError
        else:
            value = int(raw_value)
            if value < 0:
                raise ValueError
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, binascii.Error):
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Search cursor is invalid.",
            status_code=422,
            details=[
                {
                    "field": "cursor",
                    "message": "The cursor is invalid or does not match the current sort.",
                    "type": "value_error",
                }
            ],
        ) from None
    return SearchCursor(sort=expected_sort, value=value, listing_id=listing_id)
