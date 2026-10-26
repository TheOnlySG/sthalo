"""Listing lifecycle, photo, and moderation business rules."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from geoalchemy2 import Geometry
from geoalchemy2.elements import WKTElement
from sqlalchemy import cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError, ErrorCode
from app.integrations.storage.supabase import PhotoStorage, PhotoStorageError
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import record_event
from app.modules.identity.models import User
from app.modules.identity.service import CURRENT_OWNER_TERMS_VERSION
from app.modules.listings.models import (
    Listing,
    ListingPhoto,
    ListingStatus,
    ParkingListing,
    PricingModel,
    Resource,
)
from app.modules.listings.photos import PhotoValidationError, process_photo
from app.modules.listings.schemas import (
    AdminOwnerRead,
    ListingAdminRead,
    ListingCreate,
    ListingOwnerRead,
    ListingOwnerSummary,
    ListingPublicRead,
    ListingUpdate,
    ModerationAction,
    ParkingOwnerRead,
    ParkingPublicRead,
    PhotoPatch,
    PhotoRead,
)

_logger = structlog.get_logger("sthalo.listings")
MAX_PHOTOS = 8
EDITABLE_STATUSES = {
    ListingStatus.DRAFT,
    ListingStatus.ACTIVE,
    ListingStatus.PAUSED,
    ListingStatus.REJECTED,
}
PHOTO_EDITABLE_STATUSES = EDITABLE_STATUSES | {ListingStatus.PENDING_REVIEW}
PUBLISHED_OR_PAUSED = {ListingStatus.ACTIVE, ListingStatus.PAUSED}
PROTECTED_PHOTO_STATUSES = {
    ListingStatus.ACTIVE,
    ListingStatus.PAUSED,
    ListingStatus.PENDING_REVIEW,
}
MODERATION_NOTE_STATUSES = {ListingStatus.REJECTED, ListingStatus.SUSPENDED}
REQUIRED_PARKING_FIELDS = {
    "parking_type",
    "supported_vehicle_types",
    "is_covered",
    "access_method",
    "amenities",
    "restrictions",
    "pricing_model",
    "min_booking_minutes",
    "max_booking_minutes",
    "advance_booking_max_days",
}


@dataclass(frozen=True, slots=True)
class Coordinates:
    latitude: float
    longitude: float
    public_latitude: float
    public_longitude: float


async def create_listing(
    session: AsyncSession,
    user: User,
    payload: ListingCreate,
    storage: PhotoStorage,
) -> ListingOwnerRead:
    _require_owner_terms(user)
    if not payload.owner_terms_accepted:
        raise AppError(
            ErrorCode.FORBIDDEN,
            "Owner terms must be accepted before creating a listing.",
            status_code=403,
        )
    _validate_india_bounds(payload.latitude, payload.longitude)

    listing_id = uuid4()
    public_lat, public_lng = _public_point(
        listing_id,
        payload.latitude,
        payload.longitude,
    )
    listing = Listing(
        id=listing_id,
        owner_id=user.id,
        title=payload.title,
        description=payload.description,
        location=_point(payload.latitude, payload.longitude),
        public_location=_point(public_lat, public_lng),
        address_line=payload.address_line,
        locality=payload.locality,
        city=payload.city,
        state=payload.state,
        pincode=payload.pincode,
        status=ListingStatus.DRAFT,
        verification_status="unverified",
        timezone="Asia/Kolkata",
    )
    session.add(listing)
    session.add(
        ParkingListing(
            listing_id=listing_id,
            **payload.parking.model_dump(mode="json"),
        )
    )
    session.add(Resource(listing_id=listing_id, label="Main bay"))
    record_event(
        session,
        actor=user,
        action="listing.created",
        entity_type="listing",
        entity_id=listing_id,
        after={"status": ListingStatus.DRAFT.value},
    )
    await session.commit()
    _logger.info("listing_created", user_id=str(user.id), listing_id=str(listing_id))
    return await get_owner_listing(session, user, listing_id, storage)


async def list_owner_listings(
    session: AsyncSession,
    user: User,
    storage: PhotoStorage,
) -> list[ListingOwnerSummary]:
    listings = list(
        await session.scalars(
            select(Listing)
            .options(selectinload(Listing.photos))
            .where(Listing.owner_id == user.id)
            .execution_options(populate_existing=True)
            .order_by(Listing.updated_at.desc(), Listing.id)
        )
    )
    notes = await _latest_moderation_notes(session, [item.id for item in listings])
    summaries: list[ListingOwnerSummary] = []
    for listing in listings:
        cover = _cover_photo(listing)
        cover_url = await _signed_url(cover.storage_key, storage) if cover is not None else None
        summaries.append(
            ListingOwnerSummary(
                id=listing.id,
                title=listing.title,
                status=ListingStatus(listing.status),
                city=listing.city,
                locality=listing.locality,
                cover_url=cover_url,
                photo_count=len(listing.photos),
                updated_at=listing.updated_at,
                moderation_note=notes.get(listing.id),
            )
        )
    return summaries


async def get_owner_listing(
    session: AsyncSession,
    user: User,
    listing_id: UUID,
    storage: PhotoStorage,
) -> ListingOwnerRead:
    listing = await _get_owner_entity(session, user, listing_id)
    coords = await _coordinates(session, [listing.id])
    notes = await _latest_moderation_notes(session, [listing.id])
    return await _serialize_owner(
        listing,
        coords[listing.id],
        notes.get(listing.id),
        storage,
    )


async def update_listing(
    session: AsyncSession,
    user: User,
    listing_id: UUID,
    payload: ListingUpdate,
    storage: PhotoStorage,
) -> ListingOwnerRead:
    listing = await _get_owner_entity(session, user, listing_id)
    _validate_editable(listing)
    before_status = listing.status
    values = payload.model_dump(exclude_unset=True, mode="json")
    parking_values = values.pop("parking", None)
    _reject_null_required_fields(values)

    coordinates: tuple[float, float] | None = None
    if "latitude" in values:
        latitude = values.pop("latitude")
        longitude = values.pop("longitude")
        if latitude is None or longitude is None:
            raise _validation_error("latitude", "latitude and longitude cannot be null")
        _validate_india_bounds(float(latitude), float(longitude))
        coordinates = (float(latitude), float(longitude))

    for field, value in values.items():
        setattr(listing, field, value)

    if coordinates is not None:
        public_lat, public_lng = _public_point(listing.id, *coordinates)
        listing.location = _point(*coordinates)
        listing.public_location = _point(public_lat, public_lng)

    if parking_values is not None:
        if listing.parking is None:
            raise _validation_error("parking", "Parking details are missing")
        _merge_parking(listing.parking, parking_values)
        _validate_parking_shape(listing.parking)

    _mark_edited(session, user, listing)
    record_event(
        session,
        actor=user,
        action="listing.updated",
        entity_type="listing",
        entity_id=listing.id,
        before={"status": before_status},
        after={"status": listing.status, "fields": sorted(values)},
    )
    await session.commit()
    _logger.info("listing_updated", user_id=str(user.id), listing_id=str(listing.id))
    return await get_owner_listing(session, user, listing.id, storage)


async def submit_listing(
    session: AsyncSession,
    user: User,
    listing_id: UUID,
    declaration_accepted: bool,
    storage: PhotoStorage,
) -> ListingOwnerRead:
    _require_owner_terms(user)
    listing = await _get_owner_entity(session, user, listing_id)
    if listing.status not in {ListingStatus.DRAFT, ListingStatus.REJECTED}:
        raise _invalid_transition("Only draft or rejected listings can be submitted.")
    if not declaration_accepted:
        raise _incomplete("declaration_accepted", "The owner declaration is required.")
    _validate_ready_for_review(listing)
    before_status = listing.status
    listing.status = ListingStatus.PENDING_REVIEW
    listing.submitted_at = datetime.now(UTC)
    listing.approved_at = None
    listing.rejected_at = None
    listing.paused_at = None
    record_event(
        session,
        actor=user,
        action="listing.submitted",
        entity_type="listing",
        entity_id=listing.id,
        before={"status": before_status},
        after={"status": listing.status},
    )
    await session.commit()
    _logger.info("listing_submitted", user_id=str(user.id), listing_id=str(listing.id))
    return await get_owner_listing(session, user, listing.id, storage)


async def pause_listing(
    session: AsyncSession,
    user: User,
    listing_id: UUID,
    storage: PhotoStorage,
) -> ListingOwnerRead:
    listing = await _get_owner_entity(session, user, listing_id)
    if listing.status != ListingStatus.ACTIVE:
        raise _invalid_transition("Only active listings can be paused.")
    listing.status = ListingStatus.PAUSED
    listing.paused_at = datetime.now(UTC)
    record_event(
        session,
        actor=user,
        action="listing.paused",
        entity_type="listing",
        entity_id=listing.id,
        before={"status": ListingStatus.ACTIVE.value},
        after={"status": ListingStatus.PAUSED.value},
    )
    await session.commit()
    return await get_owner_listing(session, user, listing.id, storage)


async def resume_listing(
    session: AsyncSession,
    user: User,
    listing_id: UUID,
    storage: PhotoStorage,
) -> ListingOwnerRead:
    listing = await _get_owner_entity(session, user, listing_id)
    if listing.status != ListingStatus.PAUSED:
        raise _invalid_transition("Only paused listings can be resumed.")
    listing.status = ListingStatus.ACTIVE
    listing.paused_at = None
    record_event(
        session,
        actor=user,
        action="listing.resumed",
        entity_type="listing",
        entity_id=listing.id,
        before={"status": ListingStatus.PAUSED.value},
        after={"status": ListingStatus.ACTIVE.value},
    )
    await session.commit()
    return await get_owner_listing(session, user, listing.id, storage)


async def archive_listing(
    session: AsyncSession,
    user: User,
    listing_id: UUID,
    storage: PhotoStorage,
) -> ListingOwnerRead:
    listing = await _get_owner_entity(session, user, listing_id)
    if listing.status == ListingStatus.ARCHIVED:
        raise _invalid_transition("Listing is already archived.")
    if listing.status == ListingStatus.SUSPENDED:
        raise _invalid_transition("A suspended listing must be restored before archiving.")
    if await _has_future_reservations(session, listing.id):
        raise AppError(
            ErrorCode.HAS_FUTURE_BOOKINGS,
            "This listing has future bookings and cannot be archived.",
            status_code=409,
        )
    before_status = listing.status
    listing.status = ListingStatus.ARCHIVED
    listing.archived_at = datetime.now(UTC)
    record_event(
        session,
        actor=user,
        action="listing.archived",
        entity_type="listing",
        entity_id=listing.id,
        before={"status": before_status},
        after={"status": ListingStatus.ARCHIVED.value},
    )
    await session.commit()
    return await get_owner_listing(session, user, listing.id, storage)


async def get_public_listing(
    session: AsyncSession,
    listing_id: UUID,
    storage: PhotoStorage,
) -> ListingPublicRead:
    listing = await session.scalar(
        select(Listing)
        .options(
            selectinload(Listing.parking),
            selectinload(Listing.photos),
        )
        .where(
            Listing.id == listing_id,
            Listing.status == ListingStatus.ACTIVE,
        )
        .execution_options(populate_existing=True)
    )
    if listing is None:
        raise AppError(ErrorCode.NOT_FOUND, "Listing not found.", status_code=404)
    coords = await _coordinates(session, [listing.id])
    return await _serialize_public(listing, coords[listing.id], storage)


async def add_photo(
    session: AsyncSession,
    user: User,
    listing_id: UUID,
    raw: bytes,
    *,
    max_upload_bytes: int,
    storage: PhotoStorage,
) -> ListingOwnerRead:
    listing = await _get_owner_entity(session, user, listing_id)
    _validate_photo_editable(listing)
    if len(listing.photos) >= MAX_PHOTOS:
        raise _incomplete("photos", f"At most {MAX_PHOTOS} photos are allowed.")
    try:
        processed = process_photo(raw, max_bytes=max_upload_bytes)
    except PhotoValidationError as exc:
        raise AppError(
            ErrorCode.UPLOAD_INVALID,
            str(exc),
            status_code=422,
        ) from exc

    key = f"{listing.id}/{uuid4().hex}.jpg"
    try:
        await storage.upload(key, processed.data, processed.mime_type)
    except PhotoStorageError as exc:
        raise AppError(
            ErrorCode.INTERNAL_ERROR,
            "Photo storage is unavailable.",
            status_code=500,
        ) from exc

    used = {photo.position for photo in listing.photos}
    position = next(index for index in range(MAX_PHOTOS) if index not in used)
    photo = ListingPhoto(
        listing_id=listing.id,
        storage_key=key,
        mime_type=processed.mime_type,
        size_bytes=len(processed.data),
        width=processed.width,
        height=processed.height,
        position=position,
        is_cover=not listing.photos,
    )
    session.add(photo)
    _mark_edited(session, user, listing)
    record_event(
        session,
        actor=user,
        action="listing.photo_added",
        entity_type="listing",
        entity_id=listing.id,
        after={"photo_id": str(photo.id), "position": position},
    )
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        try:
            await storage.delete(key)
        except PhotoStorageError:
            _logger.exception("photo_cleanup_failed", key=key)
        raise
    return await get_owner_listing(session, user, listing.id, storage)


async def update_photo(
    session: AsyncSession,
    user: User,
    listing_id: UUID,
    photo_id: UUID,
    payload: PhotoPatch,
    storage: PhotoStorage,
) -> ListingOwnerRead:
    listing = await _get_owner_entity(session, user, listing_id)
    _validate_photo_editable(listing)
    photo = _find_photo(listing, photo_id)

    if payload.position is not None and payload.position != photo.position:
        target = next(
            (item for item in listing.photos if item.position == payload.position),
            None,
        )
        old_position = photo.position
        photo.position = payload.position
        if target is not None:
            target.position = old_position

    if payload.is_cover is True:
        for item in listing.photos:
            if item.id != photo.id and item.is_cover:
                item.is_cover = False
        await session.flush()
        photo.is_cover = True
    elif payload.is_cover is False and photo.is_cover:
        replacement = next((item for item in listing.photos if item.id != photo.id), None)
        if replacement is None:
            raise _incomplete("is_cover", "The only photo must remain the cover.")
        photo.is_cover = False
        await session.flush()
        replacement.is_cover = True

    _mark_edited(session, user, listing)
    record_event(
        session,
        actor=user,
        action="listing.photo_updated",
        entity_type="listing",
        entity_id=listing.id,
        after={"photo_id": str(photo.id), "fields": sorted(payload.model_fields_set)},
    )
    await session.commit()
    return await get_owner_listing(session, user, listing.id, storage)


async def delete_photo(
    session: AsyncSession,
    user: User,
    listing_id: UUID,
    photo_id: UUID,
    storage: PhotoStorage,
) -> None:
    listing = await _get_owner_entity(session, user, listing_id)
    _validate_photo_editable(listing)
    photo = _find_photo(listing, photo_id)
    if len(listing.photos) == 1 and listing.status in PROTECTED_PHOTO_STATUSES:
        raise _incomplete(
            "photos",
            "Add a replacement photo before deleting the last published photo.",
        )

    try:
        await storage.delete(photo.storage_key)
    except PhotoStorageError as exc:
        raise AppError(
            ErrorCode.INTERNAL_ERROR,
            "Photo storage is unavailable.",
            status_code=500,
        ) from exc

    remaining = [item for item in listing.photos if item.id != photo.id]
    was_cover = photo.is_cover
    await session.delete(photo)
    await session.flush()
    for index, item in enumerate(sorted(remaining, key=lambda value: value.position)):
        item.position = index
    if was_cover and remaining:
        sorted(remaining, key=lambda value: value.position)[0].is_cover = True
    _mark_edited(session, user, listing)
    record_event(
        session,
        actor=user,
        action="listing.photo_deleted",
        entity_type="listing",
        entity_id=listing.id,
        before={"photo_id": str(photo.id)},
    )
    await session.commit()


async def list_admin_listings(
    session: AsyncSession,
    status: ListingStatus | None,
    storage: PhotoStorage,
) -> list[ListingAdminRead]:
    statement = (
        select(Listing)
        .options(
            selectinload(Listing.parking),
            selectinload(Listing.photos),
        )
        .order_by(Listing.submitted_at.asc().nulls_last(), Listing.created_at.asc())
        .limit(100)
        .execution_options(populate_existing=True)
    )
    if status is not None:
        statement = statement.where(Listing.status == status)
    listings = list(await session.scalars(statement))
    coords = await _coordinates(session, [item.id for item in listings])
    notes = await _latest_moderation_notes(session, [item.id for item in listings])
    return [
        await _serialize_admin(
            listing,
            coords[listing.id],
            notes.get(listing.id),
            storage,
        )
        for listing in listings
    ]


async def get_admin_listing(
    session: AsyncSession,
    listing_id: UUID,
    storage: PhotoStorage,
) -> ListingAdminRead:
    listing = await _get_admin_entity(session, listing_id)
    coords = await _coordinates(session, [listing.id])
    notes = await _latest_moderation_notes(session, [listing.id])
    return await _serialize_admin(
        listing,
        coords[listing.id],
        notes.get(listing.id),
        storage,
    )


async def approve_listing(
    session: AsyncSession,
    admin: User,
    listing_id: UUID,
    action: ModerationAction,
    storage: PhotoStorage,
) -> ListingAdminRead:
    listing = await _get_admin_entity(session, listing_id)
    if listing.status != ListingStatus.PENDING_REVIEW:
        raise _invalid_transition("Only pending listings can be approved.")
    before_status = listing.status
    listing.status = ListingStatus.ACTIVE
    listing.approved_at = datetime.now(UTC)
    listing.rejected_at = None
    record_event(
        session,
        actor=admin,
        action="listing.approved",
        entity_type="listing",
        entity_id=listing.id,
        before={"status": before_status},
        after={"status": listing.status, "note": action.note},
    )
    await session.commit()
    return await get_admin_listing(session, listing_id, storage)


async def reject_listing(
    session: AsyncSession,
    admin: User,
    listing_id: UUID,
    action: ModerationAction,
    storage: PhotoStorage,
) -> ListingAdminRead:
    note = _require_moderation_note(action)
    listing = await _get_admin_entity(session, listing_id)
    if listing.status != ListingStatus.PENDING_REVIEW:
        raise _invalid_transition("Only pending listings can be rejected.")
    listing.status = ListingStatus.REJECTED
    listing.rejected_at = datetime.now(UTC)
    record_event(
        session,
        actor=admin,
        action="listing.rejected",
        entity_type="listing",
        entity_id=listing.id,
        before={"status": ListingStatus.PENDING_REVIEW.value},
        after={"status": ListingStatus.REJECTED.value, "reason": note},
    )
    await session.commit()
    return await get_admin_listing(session, listing_id, storage)


async def suspend_listing(
    session: AsyncSession,
    admin: User,
    listing_id: UUID,
    action: ModerationAction,
    storage: PhotoStorage,
) -> ListingAdminRead:
    note = _require_moderation_note(action)
    listing = await _get_admin_entity(session, listing_id)
    if listing.status not in {
        ListingStatus.ACTIVE,
        ListingStatus.PAUSED,
        ListingStatus.REJECTED,
    }:
        raise _invalid_transition("This listing cannot be suspended from its current state.")
    before_status = listing.status
    listing.status = ListingStatus.SUSPENDED
    record_event(
        session,
        actor=admin,
        action="listing.suspended",
        entity_type="listing",
        entity_id=listing.id,
        before={"status": before_status},
        after={"status": ListingStatus.SUSPENDED.value, "reason": note},
    )
    await session.commit()
    return await get_admin_listing(session, listing_id, storage)


async def restore_listing(
    session: AsyncSession,
    admin: User,
    listing_id: UUID,
    action: ModerationAction,
    storage: PhotoStorage,
) -> ListingAdminRead:
    note = _require_moderation_note(action)
    listing = await _get_admin_entity(session, listing_id)
    if listing.status != ListingStatus.SUSPENDED:
        raise _invalid_transition("Only suspended listings can be restored.")
    previous = await session.scalar(
        select(AuditEvent.before["status"].astext)
        .where(
            AuditEvent.entity_type == "listing",
            AuditEvent.entity_id == listing.id,
            AuditEvent.action == "listing.suspended",
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(1)
    )
    allowed = {
        ListingStatus.ACTIVE.value,
        ListingStatus.PAUSED.value,
        ListingStatus.REJECTED.value,
    }
    restored_status = (
        previous
        if isinstance(previous, str) and previous in allowed
        else (
            ListingStatus.ACTIVE.value
            if listing.approved_at is not None
            else ListingStatus.REJECTED.value
        )
    )
    listing.status = restored_status
    record_event(
        session,
        actor=admin,
        action="listing.restored",
        entity_type="listing",
        entity_id=listing.id,
        before={"status": ListingStatus.SUSPENDED.value},
        after={"status": restored_status, "reason": note},
    )
    await session.commit()
    return await get_admin_listing(session, listing_id, storage)


async def _get_owner_entity(
    session: AsyncSession,
    user: User,
    listing_id: UUID,
) -> Listing:
    listing = await session.scalar(
        select(Listing)
        .options(
            selectinload(Listing.parking),
            selectinload(Listing.photos),
        )
        .where(Listing.id == listing_id, Listing.owner_id == user.id)
        .execution_options(populate_existing=True)
    )
    if listing is None:
        raise AppError(ErrorCode.NOT_FOUND, "Listing not found.", status_code=404)
    return listing


async def _get_admin_entity(session: AsyncSession, listing_id: UUID) -> Listing:
    listing = await session.scalar(
        select(Listing)
        .options(
            selectinload(Listing.parking),
            selectinload(Listing.photos),
        )
        .where(Listing.id == listing_id)
        .execution_options(populate_existing=True)
    )
    if listing is None:
        raise AppError(ErrorCode.NOT_FOUND, "Listing not found.", status_code=404)
    return listing


async def _serialize_owner(
    listing: Listing,
    coords: Coordinates,
    moderation_note: str | None,
    storage: PhotoStorage,
) -> ListingOwnerRead:
    if listing.parking is None:
        raise RuntimeError("Listing parking attributes are missing")
    photos = await _photo_reads(listing.photos, storage)
    parking = _parking_owner_read(listing.parking)
    return ListingOwnerRead(
        id=listing.id,
        title=listing.title,
        description=listing.description,
        status=ListingStatus(listing.status),
        latitude=coords.latitude,
        longitude=coords.longitude,
        address_line=listing.address_line,
        locality=listing.locality,
        city=listing.city,
        state=listing.state,
        pincode=listing.pincode,
        parking=parking,
        photos=photos,
        moderation_note=(moderation_note if listing.status in MODERATION_NOTE_STATUSES else None),
        submitted_at=listing.submitted_at,
        approved_at=listing.approved_at,
        rejected_at=listing.rejected_at,
        paused_at=listing.paused_at,
        archived_at=listing.archived_at,
        created_at=listing.created_at,
        updated_at=listing.updated_at,
    )


async def _serialize_public(
    listing: Listing,
    coords: Coordinates,
    storage: PhotoStorage,
) -> ListingPublicRead:
    if listing.parking is None:
        raise RuntimeError("Listing parking attributes are missing")
    photos = await _photo_reads(listing.photos, storage)
    return ListingPublicRead(
        id=listing.id,
        title=listing.title,
        description=listing.description,
        latitude=coords.public_latitude,
        longitude=coords.public_longitude,
        locality=listing.locality,
        city=listing.city,
        state=listing.state,
        parking=_parking_public_read(listing.parking),
        photos=photos,
        updated_at=listing.updated_at,
    )


async def _serialize_admin(
    listing: Listing,
    coords: Coordinates,
    moderation_note: str | None,
    storage: PhotoStorage,
) -> ListingAdminRead:
    owner = await _serialize_owner(listing, coords, moderation_note, storage)
    return ListingAdminRead(
        **owner.model_dump(),
        owner=AdminOwnerRead(
            id=listing.owner.id,
            email=listing.owner.email,
            full_name=listing.owner.full_name,
        ),
    )


async def _photo_reads(
    photos: list[ListingPhoto],
    storage: PhotoStorage,
) -> list[PhotoRead]:
    reads: list[PhotoRead] = []
    for photo in sorted(photos, key=lambda item: item.position):
        reads.append(
            PhotoRead(
                id=photo.id,
                url=await _signed_url(photo.storage_key, storage),
                width=photo.width,
                height=photo.height,
                position=photo.position,
                is_cover=photo.is_cover,
                mime_type=photo.mime_type,
            )
        )
    return reads


async def _signed_url(key: str, storage: PhotoStorage) -> str:
    try:
        return await storage.signed_url(key)
    except PhotoStorageError as exc:
        raise AppError(
            ErrorCode.INTERNAL_ERROR,
            "Photo storage is unavailable.",
            status_code=500,
        ) from exc


async def _coordinates(
    session: AsyncSession,
    listing_ids: list[UUID],
) -> dict[UUID, Coordinates]:
    if not listing_ids:
        return {}
    rows = (
        await session.execute(
            select(
                Listing.id,
                func.ST_Y(cast(Listing.location, Geometry)),
                func.ST_X(cast(Listing.location, Geometry)),
                func.ST_Y(cast(Listing.public_location, Geometry)),
                func.ST_X(cast(Listing.public_location, Geometry)),
            ).where(Listing.id.in_(listing_ids))
        )
    ).all()
    return {
        row[0]: Coordinates(
            latitude=float(row[1]),
            longitude=float(row[2]),
            public_latitude=float(row[3]),
            public_longitude=float(row[4]),
        )
        for row in rows
    }


async def _latest_moderation_notes(
    session: AsyncSession,
    listing_ids: list[UUID],
) -> dict[UUID, str]:
    if not listing_ids:
        return {}
    rows = await session.execute(
        select(AuditEvent.entity_id, AuditEvent.after)
        .where(
            AuditEvent.entity_type == "listing",
            AuditEvent.entity_id.in_(listing_ids),
            AuditEvent.action.in_(["listing.rejected", "listing.suspended"]),
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    )
    notes: dict[UUID, str] = {}
    for entity_id, payload in rows:
        if not isinstance(entity_id, UUID) or entity_id in notes:
            continue
        if not isinstance(payload, dict):
            continue
        reason = payload.get("reason")
        if isinstance(reason, str) and reason:
            notes[entity_id] = reason
    return notes


async def _has_future_reservations(session: AsyncSession, listing_id: UUID) -> bool:
    found = await session.scalar(
        text(
            "SELECT 1 FROM sthalo.reservations "
            "WHERE listing_id = :listing_id "
            "AND status IN ('pending_confirmation', 'confirmed', 'active') "
            "AND upper(time_range) > now() LIMIT 1"
        ),
        {"listing_id": listing_id},
    )
    return found is not None


def _cover_photo(listing: Listing) -> ListingPhoto | None:
    cover = next((photo for photo in listing.photos if photo.is_cover), None)
    if cover is not None:
        return cover
    return next(iter(sorted(listing.photos, key=lambda item: item.position)), None)


def _find_photo(listing: Listing, photo_id: UUID) -> ListingPhoto:
    photo = next((item for item in listing.photos if item.id == photo_id), None)
    if photo is None:
        raise AppError(ErrorCode.NOT_FOUND, "Photo not found.", status_code=404)
    return photo


def _require_owner_terms(user: User) -> None:
    if (
        user.owner_terms_version != CURRENT_OWNER_TERMS_VERSION
        or user.owner_terms_accepted_at is None
    ):
        raise AppError(
            ErrorCode.FORBIDDEN,
            "Current owner terms must be accepted first.",
            status_code=403,
        )


def _validate_editable(listing: Listing) -> None:
    if listing.status not in EDITABLE_STATUSES:
        raise _invalid_transition("This listing cannot be edited in its current state.")


def _validate_photo_editable(listing: Listing) -> None:
    if listing.status not in PHOTO_EDITABLE_STATUSES:
        raise _invalid_transition("Photos cannot be changed in this listing state.")


def _mark_edited(session: AsyncSession, user: User, listing: Listing) -> None:
    before_status = listing.status
    if listing.status == ListingStatus.REJECTED:
        listing.status = ListingStatus.DRAFT
        listing.rejected_at = None
    elif listing.status in PUBLISHED_OR_PAUSED:
        listing.status = ListingStatus.PENDING_REVIEW
        listing.submitted_at = datetime.now(UTC)
        listing.approved_at = None
        listing.paused_at = None
    else:
        return
    record_event(
        session,
        actor=user,
        action="listing.status_changed",
        entity_type="listing",
        entity_id=listing.id,
        before={"status": before_status},
        after={"status": listing.status},
    )


def _validate_ready_for_review(listing: Listing) -> None:
    if listing.parking is None:
        raise _incomplete("parking", "Parking details are required.")
    if not 1 <= len(listing.photos) <= MAX_PHOTOS:
        raise _incomplete("photos", "Add between 1 and 8 photos before submitting.")
    _validate_parking_shape(listing.parking)


def _merge_parking(parking: ParkingListing, values: dict[str, Any]) -> None:
    for field, value in values.items():
        if field in REQUIRED_PARKING_FIELDS and value is None:
            raise _validation_error(field, f"{field} cannot be null")
        setattr(parking, field, value)
    if not parking.supported_vehicle_types:
        raise _validation_error(
            "supported_vehicle_types",
            "At least one supported vehicle type is required",
        )


def _validate_parking_shape(parking: ParkingListing) -> None:
    if parking.max_booking_minutes < parking.min_booking_minutes:
        raise _validation_error(
            "max_booking_minutes",
            "max_booking_minutes must be at least min_booking_minutes",
        )
    if parking.pricing_model == PricingModel.HOURLY:
        if parking.price_hourly_paise is None or parking.price_daily_cap_paise is not None:
            raise _validation_error(
                "pricing_model",
                "Hourly pricing requires only the hourly price",
            )
    elif parking.pricing_model == PricingModel.HOURLY_WITH_DAILY_CAP:
        if parking.price_hourly_paise is None or parking.price_daily_cap_paise is None:
            raise _validation_error(
                "pricing_model",
                "Hourly-with-cap pricing requires both prices",
            )
        if parking.price_daily_cap_paise < parking.price_hourly_paise:
            raise _validation_error(
                "price_daily_cap_paise",
                "Daily cap cannot be lower than the hourly price",
            )
    elif parking.price_hourly_paise is not None or parking.price_daily_cap_paise is None:
        raise _validation_error(
            "pricing_model",
            "Flat-daily pricing requires only the daily price",
        )


def _parking_public_read(parking: ParkingListing) -> ParkingPublicRead:
    return ParkingPublicRead.model_validate(
        {
            "parking_type": parking.parking_type,
            "supported_vehicle_types": parking.supported_vehicle_types,
            "max_length_mm": parking.max_length_mm,
            "max_width_mm": parking.max_width_mm,
            "max_height_mm": parking.max_height_mm,
            "is_covered": parking.is_covered,
            "access_method": parking.access_method,
            "amenities": parking.amenities,
            "restrictions": parking.restrictions,
            "pricing_model": parking.pricing_model,
            "price_hourly_paise": parking.price_hourly_paise,
            "price_daily_cap_paise": parking.price_daily_cap_paise,
            "min_booking_minutes": parking.min_booking_minutes,
            "max_booking_minutes": parking.max_booking_minutes,
            "advance_booking_max_days": parking.advance_booking_max_days,
        }
    )


def _parking_owner_read(parking: ParkingListing) -> ParkingOwnerRead:
    return ParkingOwnerRead(
        **_parking_public_read(parking).model_dump(),
        access_instructions=parking.access_instructions,
    )


def _validate_india_bounds(latitude: float, longitude: float) -> None:
    if not 6.0 <= latitude <= 38.0 or not 68.0 <= longitude <= 98.0:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "The listing location must be inside India.",
            status_code=422,
            details=[
                {
                    "field": "latitude/longitude",
                    "message": "Coordinates are outside the supported India bounds.",
                    "type": "value_error",
                }
            ],
        )


def _public_point(
    listing_id: UUID,
    latitude: float,
    longitude: float,
) -> tuple[float, float]:
    rng = random.Random(listing_id.int)
    distance_m = rng.uniform(80.0, 200.0)
    bearing = rng.uniform(0.0, 2.0 * math.pi)
    delta_lat = (distance_m * math.cos(bearing)) / 111_320.0
    delta_lng = (distance_m * math.sin(bearing)) / (
        111_320.0 * max(math.cos(math.radians(latitude)), 0.01)
    )
    return latitude + delta_lat, longitude + delta_lng


def _point(latitude: float, longitude: float) -> WKTElement:
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


def _reject_null_required_fields(values: dict[str, Any]) -> None:
    for field in (
        "title",
        "description",
        "address_line",
        "locality",
        "city",
        "state",
        "pincode",
    ):
        if field in values and values[field] is None:
            raise _validation_error(field, f"{field} cannot be null")


def _require_moderation_note(action: ModerationAction) -> str:
    if action.note is None:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "A moderation note is required for this action.",
            status_code=422,
            details=[
                {
                    "field": "note",
                    "message": "A moderation note is required.",
                    "type": "value_error",
                }
            ],
        )
    return action.note


def _invalid_transition(message: str) -> AppError:
    return AppError(
        ErrorCode.INVALID_STATE_TRANSITION,
        message,
        status_code=409,
    )


def _incomplete(field: str, message: str) -> AppError:
    return AppError(
        ErrorCode.INCOMPLETE_LISTING,
        "Listing is not ready for this action.",
        status_code=422,
        details=[{"field": field, "message": message, "type": "value_error"}],
    )


def _validation_error(field: str, message: str) -> AppError:
    return AppError(
        ErrorCode.VALIDATION_ERROR,
        "Request validation failed.",
        status_code=422,
        details=[{"field": field, "message": message, "type": "value_error"}],
    )
