"""Reservation quoting, hold creation, lifecycle transitions, and serialization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.modules.audit.service import record_event
from app.modules.availability.service import is_listing_window_available
from app.modules.identity.models import User
from app.modules.listings.models import (
    Listing,
    ListingStatus,
    ParkingListing,
    PricingModel,
    Reservation,
    ReservationStatus,
    Resource,
)
from app.modules.profiles.models import Vehicle, VehicleType
from app.modules.reservations.idempotency import (
    claim_idempotency,
    discard_idempotency,
    request_fingerprint,
    store_idempotency_response,
)
from app.modules.reservations.schemas import (
    PriceBreakdown,
    ReservationCreate,
    ReservationListingRead,
    ReservationQuote,
    ReservationRead,
    ReservationVehicleRead,
    ReservationWindowRequest,
)

HOLD_DURATION = timedelta(minutes=10)
REVEAL_STATUSES = {
    ReservationStatus.CONFIRMED,
    ReservationStatus.ACTIVE,
    ReservationStatus.COMPLETED,
}
LIVE_STATUSES = (
    ReservationStatus.PENDING_CONFIRMATION,
    ReservationStatus.CONFIRMED,
    ReservationStatus.ACTIVE,
)
TERMINAL_STATUSES = {
    ReservationStatus.COMPLETED,
    ReservationStatus.CANCELLED,
    ReservationStatus.EXPIRED,
}
LIST_LIMIT = 100
RECONCILE_LIMIT = 250


@dataclass
class BookingContext:
    listing: Listing
    parking: ParkingListing
    vehicle: Vehicle


def _validation(field: str, message: str) -> AppError:
    return AppError(
        ErrorCode.VALIDATION_ERROR,
        "Request validation failed.",
        status_code=422,
        details=[{"field": field, "message": message, "type": "value_error"}],
    )


async def _db_now(session: AsyncSession) -> datetime:
    value = await session.scalar(select(func.now()))
    if not isinstance(value, datetime):
        raise RuntimeError("Database clock is unavailable")
    return value.astimezone(UTC)


def _range_bounds(value: Any) -> tuple[datetime, datetime]:
    lower = getattr(value, "lower", None)
    upper = getattr(value, "upper", None)
    if isinstance(lower, datetime) and isinstance(upper, datetime):
        return lower, upper
    raise RuntimeError("Reservation has no time range bounds")


def _estimated_state(now: datetime, start: datetime, end: datetime, status: str) -> str:
    if status == ReservationStatus.CONFIRMED and start <= now:
        return ReservationStatus.ACTIVE
    if status == ReservationStatus.ACTIVE and end <= now:
        return ReservationStatus.COMPLETED
    return status


async def calculate_price(
    parking: ParkingListing,
    start: datetime,
    end: datetime,
) -> PriceBreakdown:
    duration_minutes = int((end - start).total_seconds() // 60)
    billable_minutes = ((duration_minutes + 14) // 15) * 15
    chargeable_days = max(1, (duration_minutes + 1439) // 1440)
    hourly_rate = parking.price_hourly_paise
    daily_cap = parking.price_daily_cap_paise
    hourly_component = 0
    cap_component = 0

    if hourly_rate is not None:
        hourly_component = (hourly_rate * billable_minutes + 30) // 60
    if daily_cap is not None:
        cap_component = daily_cap * chargeable_days

    model = PricingModel(parking.pricing_model)
    if model == PricingModel.HOURLY:
        assert hourly_rate is not None
        total = hourly_component
        calculation = f"{billable_minutes} billable minutes at INR {hourly_rate / 100:.2f} per hour"
    elif model == PricingModel.HOURLY_WITH_DAILY_CAP:
        assert hourly_rate is not None
        assert daily_cap is not None
        total = min(hourly_component, cap_component)
        calculation = (
            f"{billable_minutes} billable minutes at INR {hourly_rate / 100:.2f} per hour, "
            f"capped at INR {daily_cap / 100:.2f} per day for {chargeable_days} day(s)"
        )
    else:
        assert daily_cap is not None
        total = cap_component
        calculation = f"{chargeable_days} day(s) at INR {daily_cap / 100:.2f} per day"

    return PriceBreakdown(
        pricing_model=model,
        duration_minutes=duration_minutes,
        billable_minutes=billable_minutes,
        chargeable_days=chargeable_days,
        hourly_rate_paise=hourly_rate,
        daily_cap_paise=daily_cap,
        hourly_component_paise=hourly_component,
        cap_component_paise=cap_component,
        total_paise=int(total),
        calculation=calculation,
    )


async def _load_context(
    session: AsyncSession,
    user: User,
    payload: ReservationWindowRequest,
) -> BookingContext:
    listing = await session.get(Listing, payload.listing_id)
    if listing is None:
        raise AppError(ErrorCode.NOT_FOUND, "Listing not found.", status_code=404)
    if listing.owner_id == user.id:
        raise AppError(
            ErrorCode.OWN_LISTING,
            "You cannot book your own parking listing.",
            status_code=403,
        )
    if listing.status != ListingStatus.ACTIVE:
        raise AppError(
            ErrorCode.LISTING_NOT_ACTIVE,
            "This listing is not accepting reservations.",
            status_code=409,
        )
    parking = await session.get(ParkingListing, listing.id)
    if parking is None:
        raise AppError(
            ErrorCode.INCOMPLETE_LISTING,
            "This listing is not ready for reservations.",
            status_code=409,
        )
    vehicle = await session.scalar(
        select(Vehicle).where(
            Vehicle.id == payload.vehicle_id,
            Vehicle.user_id == user.id,
        )
    )
    if vehicle is None:
        raise AppError(ErrorCode.NOT_FOUND, "Vehicle not found.", status_code=404)

    now = await _db_now(session)
    if payload.start < now:
        raise _validation("start", "start must be in the future")
    zone = ZoneInfo(listing.timezone)
    start_local = payload.start.astimezone(zone)
    now_local = now.astimezone(zone)
    if start_local.date() > now_local.date() + timedelta(days=parking.advance_booking_max_days):
        raise _validation(
            "start",
            f"Bookings can be made at most {parking.advance_booking_max_days} days ahead",
        )

    duration_minutes = int((payload.end - payload.start).total_seconds() // 60)
    if duration_minutes < parking.min_booking_minutes:
        raise _validation(
            "end",
            f"The minimum booking duration is {parking.min_booking_minutes} minutes",
        )
    if duration_minutes > parking.max_booking_minutes:
        raise _validation(
            "end",
            f"The maximum booking duration is {parking.max_booking_minutes} minutes",
        )

    if vehicle.vehicle_type not in parking.supported_vehicle_types:
        raise AppError(
            ErrorCode.VEHICLE_DOES_NOT_FIT,
            "This vehicle type is not supported by the listing.",
            status_code=422,
            details=[
                {
                    "field": "vehicle_id",
                    "message": "This vehicle type is not supported by the listing.",
                    "type": "value_error",
                }
            ],
        )
    for vehicle_value, max_value, label in (
        (vehicle.length_mm, parking.max_length_mm, "length"),
        (vehicle.width_mm, parking.max_width_mm, "width"),
        (vehicle.height_mm, parking.max_height_mm, "height"),
    ):
        if vehicle_value is not None and max_value is not None and vehicle_value > max_value:
            raise AppError(
                ErrorCode.VEHICLE_DOES_NOT_FIT,
                f"This vehicle exceeds the listing's maximum {label}.",
                status_code=422,
                details=[
                    {
                        "field": "vehicle_id",
                        "message": f"This vehicle exceeds the maximum {label}.",
                        "type": "value_error",
                    }
                ],
            )
    return BookingContext(listing=listing, parking=parking, vehicle=vehicle)


async def _check_availability(
    session: AsyncSession,
    listing: Listing,
    start: datetime,
    end: datetime,
) -> None:
    available = await is_listing_window_available(session, listing, start, end)
    if not available:
        raise AppError(
            ErrorCode.SLOT_UNAVAILABLE,
            "The requested window is not available.",
            status_code=409,
        )


async def quote_reservation(
    session: AsyncSession,
    user: User,
    payload: ReservationWindowRequest,
) -> ReservationQuote:
    context = await _load_context(session, user, payload)
    await _check_availability(session, context.listing, payload.start, payload.end)
    price = await calculate_price(context.parking, payload.start, payload.end)
    return ReservationQuote(
        listing_id=context.listing.id,
        start=payload.start,
        end=payload.end,
        base_amount_paise=price.total_paise,
        total_paise=price.total_paise,
        price=price,
    )


async def _lock_resource(session: AsyncSession, listing_id: UUID) -> Resource:
    resource = await session.scalar(
        select(Resource)
        .where(Resource.listing_id == listing_id, Resource.is_active.is_(True))
        .order_by(Resource.created_at, Resource.id)
        .limit(1)
        .with_for_update()
    )
    if resource is None:
        raise AppError(
            ErrorCode.INVALID_STATE_TRANSITION,
            "Listing has no bookable resource.",
            status_code=409,
        )
    return resource


async def _expire_resource_holds(
    session: AsyncSession,
    resource_id: UUID,
    now: datetime,
) -> int:
    rows = (
        await session.execute(
            update(Reservation)
            .where(
                Reservation.resource_id == resource_id,
                Reservation.status == ReservationStatus.PENDING_CONFIRMATION,
                Reservation.hold_expires_at <= now,
            )
            .values(
                status=ReservationStatus.EXPIRED,
                expired_at=now,
                updated_at=now,
            )
            .returning(Reservation.id, Reservation.reference)
        )
    ).all()
    for reservation_id, reference in rows:
        record_event(
            session,
            actor=None,
            action="reservation.expired",
            entity_type="reservation",
            entity_id=reservation_id,
            before={"status": ReservationStatus.PENDING_CONFIRMATION.value},
            after={
                "status": ReservationStatus.EXPIRED.value,
                "reference": reference,
            },
        )
    return len(rows)


async def create_reservation(
    session: AsyncSession,
    user: User,
    payload: ReservationCreate,
    idempotency_key: str,
) -> tuple[ReservationRead, int]:
    fingerprint = request_fingerprint("reservation.create", payload.model_dump(mode="json"))
    claim = await claim_idempotency(
        session,
        user=user,
        key=idempotency_key,
        fingerprint=fingerprint,
    )
    if claim.replay is not None and claim.replay_status is not None:
        return ReservationRead.model_validate(claim.replay), claim.replay_status

    context = await _load_context(session, user, payload)
    resource = await _lock_resource(session, context.listing.id)
    now = await _db_now(session)
    await _expire_resource_holds(session, resource.id, now)
    await _check_availability(session, context.listing, payload.start, payload.end)
    price = await calculate_price(context.parking, payload.start, payload.end)

    reservation_id = uuid4()
    reservation = Reservation(
        id=reservation_id,
        reference=f"STH-{now:%Y%m%d}-{reservation_id.hex[:8].upper()}",
        customer_id=user.id,
        owner_id=context.listing.owner_id,
        listing_id=context.listing.id,
        resource_id=resource.id,
        vehicle_id=context.vehicle.id,
        time_range=func.tstzrange(payload.start, payload.end, "[)"),
        status=ReservationStatus.PENDING_CONFIRMATION,
        hold_expires_at=now + HOLD_DURATION,
        currency="INR",
        base_amount_paise=price.total_paise,
        total_paise=price.total_paise,
        price_snapshot=price.model_dump(mode="json"),
    )
    session.add(reservation)
    try:
        await session.flush()
    except IntegrityError as exc:
        sqlstate = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
        await session.rollback()
        if sqlstate == "23P01":
            raise AppError(
                ErrorCode.SLOT_UNAVAILABLE,
                "The requested window was just reserved.",
                status_code=409,
            ) from exc
        raise
    await session.refresh(reservation)
    record_event(
        session,
        actor=user,
        action="reservation.created",
        entity_type="reservation",
        entity_id=reservation.id,
        after={
            "reference": reservation.reference,
            "status": reservation.status,
            "start": payload.start.isoformat(),
            "end": payload.end.isoformat(),
            "total_paise": reservation.total_paise,
        },
    )
    read = await serialize_reservation(session, reservation, user, now=now)
    await store_idempotency_response(
        session,
        claim.row,
        status_code=201,
        body=read.model_dump(mode="json"),
    )
    await session.commit()
    return read, 201


async def confirm_reservation(
    session: AsyncSession,
    user: User,
    reservation_id: UUID,
    idempotency_key: str,
) -> tuple[ReservationRead, int]:
    fingerprint = request_fingerprint(
        "reservation.confirm",
        {"reservation_id": str(reservation_id), "customer_id": str(user.id)},
    )
    claim = await claim_idempotency(
        session,
        user=user,
        key=idempotency_key,
        fingerprint=fingerprint,
    )
    if claim.replay is not None and claim.replay_status is not None:
        return ReservationRead.model_validate(claim.replay), claim.replay_status

    reservation = await session.scalar(
        select(Reservation).where(Reservation.id == reservation_id).with_for_update()
    )
    if reservation is None or reservation.customer_id != user.id:
        raise AppError(ErrorCode.NOT_FOUND, "Reservation not found.", status_code=404)

    now = await _db_now(session)
    if reservation.status == ReservationStatus.CONFIRMED:
        read = await serialize_reservation(session, reservation, user, now=now)
        await store_idempotency_response(
            session, claim.row, status_code=200, body=read.model_dump(mode="json")
        )
        await session.commit()
        return read, 200
    if reservation.status != ReservationStatus.PENDING_CONFIRMATION:
        raise AppError(
            ErrorCode.INVALID_STATE_TRANSITION,
            "Only a pending reservation can be confirmed.",
            status_code=409,
        )
    if reservation.hold_expires_at is None or reservation.hold_expires_at <= now:
        reservation.status = ReservationStatus.EXPIRED
        reservation.expired_at = now
        reservation.updated_at = now
        record_event(
            session,
            actor=None,
            action="reservation.expired",
            entity_type="reservation",
            entity_id=reservation.id,
            before={"status": ReservationStatus.PENDING_CONFIRMATION.value},
            after={"status": ReservationStatus.EXPIRED.value},
        )
        await discard_idempotency(session, claim.row)
        await session.commit()
        raise AppError(
            ErrorCode.HOLD_EXPIRED,
            "The reservation hold has expired.",
            status_code=409,
        )

    reservation.status = ReservationStatus.CONFIRMED
    reservation.confirmed_at = now
    reservation.updated_at = now
    record_event(
        session,
        actor=user,
        action="reservation.confirmed",
        entity_type="reservation",
        entity_id=reservation.id,
        before={"status": ReservationStatus.PENDING_CONFIRMATION.value},
        after={"status": ReservationStatus.CONFIRMED.value},
    )
    read = await serialize_reservation(session, reservation, user, now=now)
    await store_idempotency_response(
        session, claim.row, status_code=200, body=read.model_dump(mode="json")
    )
    await session.commit()
    return read, 200


async def cancel_reservation(
    session: AsyncSession,
    user: User,
    reservation_id: UUID,
    reason: str | None,
    idempotency_key: str,
) -> tuple[ReservationRead, int]:
    fingerprint = request_fingerprint(
        "reservation.cancel",
        {"reservation_id": str(reservation_id), "reason": reason, "actor_id": str(user.id)},
    )
    claim = await claim_idempotency(
        session,
        user=user,
        key=idempotency_key,
        fingerprint=fingerprint,
    )
    if claim.replay is not None and claim.replay_status is not None:
        return ReservationRead.model_validate(claim.replay), claim.replay_status

    reservation = await session.scalar(
        select(Reservation).where(Reservation.id == reservation_id).with_for_update()
    )
    if reservation is None:
        raise AppError(ErrorCode.NOT_FOUND, "Reservation not found.", status_code=404)

    if user.is_admin:
        role = "admin"
    elif reservation.customer_id == user.id:
        role = "customer"
    elif reservation.owner_id == user.id:
        role = "owner"
    else:
        raise AppError(ErrorCode.NOT_FOUND, "Reservation not found.", status_code=404)

    now = await _db_now(session)
    start, _ = _range_bounds(reservation.time_range)
    if reservation.status in TERMINAL_STATUSES:
        raise AppError(
            ErrorCode.INVALID_STATE_TRANSITION,
            "This reservation can no longer be cancelled.",
            status_code=409,
        )
    if (
        reservation.status == ReservationStatus.PENDING_CONFIRMATION
        and reservation.hold_expires_at is not None
        and reservation.hold_expires_at <= now
    ):
        reservation.status = ReservationStatus.EXPIRED
        reservation.expired_at = now
        reservation.updated_at = now
        record_event(
            session,
            actor=None,
            action="reservation.expired",
            entity_type="reservation",
            entity_id=reservation.id,
            before={"status": ReservationStatus.PENDING_CONFIRMATION.value},
            after={"status": ReservationStatus.EXPIRED.value},
        )
        await discard_idempotency(session, claim.row)
        await session.commit()
        raise AppError(
            ErrorCode.HOLD_EXPIRED,
            "The reservation hold has expired.",
            status_code=409,
        )

    if role in {"customer", "owner"} and (
        reservation.status == ReservationStatus.ACTIVE or now >= start
    ):
        raise AppError(
            ErrorCode.INVALID_STATE_TRANSITION,
            "A started reservation can only be cancelled by an administrator.",
            status_code=409,
        )
    if role in {"owner", "admin"} and reason is None:
        raise _validation("reason", "A cancellation reason is required for owners and admins")

    previous_status = reservation.status
    reservation.status = ReservationStatus.CANCELLED
    reservation.cancelled_by = user.id
    reservation.cancel_reason = reason
    reservation.cancelled_at = now
    reservation.updated_at = now
    record_event(
        session,
        actor=user,
        action="reservation.cancelled",
        entity_type="reservation",
        entity_id=reservation.id,
        before={"status": previous_status},
        after={
            "status": ReservationStatus.CANCELLED.value,
            "reason": reason,
            "cancelled_by_role": role,
        },
    )
    read = await serialize_reservation(session, reservation, user, now=now)
    await store_idempotency_response(
        session, claim.row, status_code=200, body=read.model_dump(mode="json")
    )
    await session.commit()
    return read, 200


async def _reconcile_selected(
    session: AsyncSession,
    *,
    customer_id: UUID | None = None,
    owner_id: UUID | None = None,
    reservation_ids: list[UUID] | None = None,
) -> bool:
    now = await _db_now(session)
    changed = False

    def scope(statement: Any) -> Any:
        if reservation_ids is not None:
            return statement.where(Reservation.id.in_(reservation_ids))
        if customer_id is not None:
            return statement.where(Reservation.customer_id == customer_id)
        if owner_id is not None:
            return statement.where(Reservation.owner_id == owner_id)
        return statement

    expired_result = await session.execute(
        scope(
            update(Reservation).where(
                Reservation.status == ReservationStatus.PENDING_CONFIRMATION,
                Reservation.hold_expires_at <= now,
            )
        )
        .values(status=ReservationStatus.EXPIRED, expired_at=now, updated_at=now)
        .returning(Reservation.id)
    )
    expired_ids: list[UUID] = list(expired_result.scalars())
    for reservation_id in expired_ids:
        changed = True
        record_event(
            session,
            actor=None,
            action="reservation.expired",
            entity_type="reservation",
            entity_id=reservation_id,
            before={"status": ReservationStatus.PENDING_CONFIRMATION.value},
            after={"status": ReservationStatus.EXPIRED.value},
        )

    started_result = await session.execute(
        scope(
            update(Reservation).where(
                Reservation.status == ReservationStatus.CONFIRMED,
                func.lower(Reservation.time_range) <= now,
            )
        )
        .values(status=ReservationStatus.ACTIVE, started_at=now, updated_at=now)
        .returning(Reservation.id)
    )
    started_ids: list[UUID] = list(started_result.scalars())
    for reservation_id in started_ids:
        changed = True
        record_event(
            session,
            actor=None,
            action="reservation.started",
            entity_type="reservation",
            entity_id=reservation_id,
            before={"status": ReservationStatus.CONFIRMED.value},
            after={"status": ReservationStatus.ACTIVE.value},
        )

    completed_result = await session.execute(
        scope(
            update(Reservation).where(
                Reservation.status == ReservationStatus.ACTIVE,
                func.upper(Reservation.time_range) <= now,
            )
        )
        .values(status=ReservationStatus.COMPLETED, completed_at=now, updated_at=now)
        .returning(Reservation.id)
    )
    completed_ids: list[UUID] = list(completed_result.scalars())
    for reservation_id in completed_ids:
        changed = True
        record_event(
            session,
            actor=None,
            action="reservation.completed",
            entity_type="reservation",
            entity_id=reservation_id,
            before={"status": ReservationStatus.ACTIVE.value},
            after={"status": ReservationStatus.COMPLETED.value},
        )

    if changed:
        await session.commit()
    return changed


async def reconcile_reservation(session: AsyncSession, reservation_id: UUID) -> None:
    await _reconcile_selected(session, reservation_ids=[reservation_id])


async def get_reservation(
    session: AsyncSession,
    user: User,
    reservation_id: UUID,
) -> ReservationRead:
    await reconcile_reservation(session, reservation_id)
    reservation = await session.get(Reservation, reservation_id)
    if reservation is None:
        raise AppError(ErrorCode.NOT_FOUND, "Reservation not found.", status_code=404)
    now = await _db_now(session)
    return await serialize_reservation(session, reservation, user, now=now)


async def _list_ids(
    session: AsyncSession,
    *,
    customer_id: UUID | None = None,
    owner_id: UUID | None = None,
) -> list[UUID]:
    statement = (
        select(Reservation.id).order_by(Reservation.created_at.desc()).limit(RECONCILE_LIMIT)
    )
    if customer_id is not None:
        statement = statement.where(Reservation.customer_id == customer_id)
    if owner_id is not None:
        statement = statement.where(Reservation.owner_id == owner_id)
    return list(await session.scalars(statement))


async def list_customer_reservations(
    session: AsyncSession,
    user: User,
    status: ReservationStatus | None = None,
) -> list[ReservationRead]:
    ids = await _list_ids(session, customer_id=user.id)
    await _reconcile_selected(session, reservation_ids=ids)
    statement = (
        select(Reservation)
        .where(Reservation.customer_id == user.id)
        .order_by(Reservation.created_at.desc())
        .limit(LIST_LIMIT)
    )
    if status is not None:
        statement = statement.where(Reservation.status == status)
    rows = list(await session.scalars(statement))
    now = await _db_now(session)
    return [await serialize_reservation(session, row, user, now=now) for row in rows]


async def list_owner_reservations(
    session: AsyncSession,
    user: User,
    status: ReservationStatus | None = None,
) -> list[ReservationRead]:
    ids = await _list_ids(session, owner_id=user.id)
    await _reconcile_selected(session, reservation_ids=ids)
    statement = (
        select(Reservation)
        .where(Reservation.owner_id == user.id)
        .order_by(Reservation.created_at.desc())
        .limit(LIST_LIMIT)
    )
    if status is not None:
        statement = statement.where(Reservation.status == status)
    rows = list(await session.scalars(statement))
    now = await _db_now(session)
    return [await serialize_reservation(session, row, user, now=now) for row in rows]


async def _coordinates(
    session: AsyncSession,
    listing: Listing,
    *,
    exact: bool,
) -> tuple[float, float]:
    column = Listing.location if exact else Listing.public_location
    row = (
        await session.execute(
            select(func.ST_Y(cast(column, Geometry)), func.ST_X(cast(column, Geometry))).where(
                Listing.id == listing.id
            )
        )
    ).one()
    return float(row[1]), float(row[0])


async def serialize_reservation(
    session: AsyncSession,
    reservation: Reservation,
    viewer: User,
    *,
    now: datetime,
) -> ReservationRead:
    if viewer.is_admin:
        role = "admin"
    elif viewer.id == reservation.customer_id:
        role = "customer"
    elif viewer.id == reservation.owner_id:
        role = "owner"
    else:
        raise AppError(ErrorCode.NOT_FOUND, "Reservation not found.", status_code=404)

    listing = await session.get(Listing, reservation.listing_id)
    parking = await session.get(ParkingListing, reservation.listing_id)
    vehicle = await session.get(Vehicle, reservation.vehicle_id)
    customer = await session.get(User, reservation.customer_id)
    owner = await session.get(User, reservation.owner_id)
    if listing is None or parking is None or vehicle is None or customer is None or owner is None:
        raise RuntimeError("Reservation references missing related records")

    public_latitude, public_longitude = await _coordinates(session, listing, exact=False)
    start, end = _range_bounds(reservation.time_range)
    status = reservation.status
    effective_status = _estimated_state(now, start, end, status)
    reveal_exact = (status in REVEAL_STATUSES and role == "customer") or role in {"owner", "admin"}
    exact_latitude: float | None = None
    exact_longitude: float | None = None
    if reveal_exact:
        exact_latitude, exact_longitude = await _coordinates(session, listing, exact=True)

    can_cancel = status not in TERMINAL_STATUSES
    if role in {"customer", "owner"}:
        can_cancel = (
            can_cancel
            and status
            in {
                ReservationStatus.PENDING_CONFIRMATION,
                ReservationStatus.CONFIRMED,
            }
            and now < start
        )
    can_confirm = (
        role == "customer"
        and status == ReservationStatus.PENDING_CONFIRMATION
        and reservation.hold_expires_at is not None
        and reservation.hold_expires_at > now
    )

    return ReservationRead(
        id=reservation.id,
        reference=reservation.reference,
        status=effective_status,
        viewer_role=role,
        listing=ReservationListingRead(
            id=listing.id,
            title=listing.title,
            locality=listing.locality,
            city=listing.city,
            latitude=public_latitude,
            longitude=public_longitude,
        ),
        vehicle=ReservationVehicleRead(
            id=vehicle.id,
            vehicle_type=VehicleType(vehicle.vehicle_type),
            registration_no=vehicle.registration_no,
            length_mm=vehicle.length_mm,
            width_mm=vehicle.width_mm,
            height_mm=vehicle.height_mm,
            is_ev=vehicle.is_ev,
        ),
        customer_name=customer.full_name if role in {"owner", "admin"} else None,
        owner_name=owner.full_name,
        start=start,
        end=end,
        hold_expires_at=reservation.hold_expires_at,
        currency="INR",
        base_amount_paise=reservation.base_amount_paise,
        total_paise=reservation.total_paise,
        price_snapshot=reservation.price_snapshot,
        can_confirm=can_confirm,
        can_cancel=can_cancel,
        exact_address=listing.address_line if reveal_exact else None,
        pincode=listing.pincode if reveal_exact else None,
        exact_latitude=exact_latitude,
        exact_longitude=exact_longitude,
        access_instructions=parking.access_instructions if reveal_exact else None,
        cancel_reason=reservation.cancel_reason,
        confirmed_at=reservation.confirmed_at,
        started_at=reservation.started_at,
        completed_at=reservation.completed_at,
        cancelled_at=reservation.cancelled_at,
        expired_at=reservation.expired_at,
        created_at=reservation.created_at,
    )


async def reconcile_all(session: AsyncSession) -> bool:
    """Run due lifecycle transitions for every reservation."""
    return await _reconcile_selected(session)


async def list_admin_reservations(
    session: AsyncSession,
    user: User,
    *,
    status: ReservationStatus | None = None,
    listing_id: UUID | None = None,
) -> list[ReservationRead]:
    statement = (
        select(Reservation.id).order_by(Reservation.created_at.desc()).limit(RECONCILE_LIMIT)
    )
    if status is not None:
        statement = statement.where(Reservation.status == status)
    if listing_id is not None:
        statement = statement.where(Reservation.listing_id == listing_id)
    ids = list(await session.scalars(statement))
    await _reconcile_selected(session, reservation_ids=ids)

    rows_statement = select(Reservation).order_by(Reservation.created_at.desc()).limit(LIST_LIMIT)
    if status is not None:
        rows_statement = rows_statement.where(Reservation.status == status)
    if listing_id is not None:
        rows_statement = rows_statement.where(Reservation.listing_id == listing_id)
    rows = list(await session.scalars(rows_statement))
    now = await _db_now(session)
    return [await serialize_reservation(session, row, user, now=now) for row in rows]
