"""Availability computation and owner rule/block management."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from typing import cast as type_cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.modules.audit.service import record_event
from app.modules.availability.models import AvailabilityRule, BlockedInterval
from app.modules.availability.schemas import (
    AvailabilityResponse,
    AvailabilityRuleInput,
    AvailabilityRuleRead,
    AvailabilityRulesPayload,
    AvailabilityWindow,
    BlockCreate,
    BlockRead,
)
from app.modules.identity.models import User
from app.modules.listings.models import Listing, ListingStatus, Reservation, Resource

Interval = tuple[datetime, datetime]
LIVE_RESERVATION_STATUSES = ("confirmed", "active")


class AvailabilityOverlapError(Exception):
    """A blocked interval overlaps another block after a race."""


def _validate_rule_overlaps(rules: list[AvailabilityRuleInput]) -> None:
    for index, rule in enumerate(rules):
        for other in rules[index + 1 :]:
            if rule.weekday != other.weekday:
                continue
            if not _dates_overlap(rule, other):
                continue
            if rule.start_time < other.end_time and other.start_time < rule.end_time:
                raise AppError(
                    ErrorCode.VALIDATION_ERROR,
                    "Availability rules overlap.",
                    status_code=422,
                    details=[
                        {
                            "field": "rules",
                            "message": (
                                "Rules on the same weekday must not overlap "
                                "while their validity dates overlap."
                            ),
                            "type": "value_error",
                        }
                    ],
                )


def _dates_overlap(a: AvailabilityRuleInput, b: AvailabilityRuleInput) -> bool:
    a_start = a.valid_from or date.min
    a_end = a.valid_to or date.max
    b_start = b.valid_from or date.min
    b_end = b.valid_to or date.max
    return a_start <= b_end and b_start <= a_end


def _merge(intervals: list[Interval]) -> list[Interval]:
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        current_start, current_end = merged[-1]
        if start <= current_end:
            merged[-1] = (current_start, max(current_end, end))
        else:
            merged.append((start, end))
    return merged


def _subtract(available: list[Interval], busy: list[Interval]) -> list[Interval]:
    result = available
    for busy_start, busy_end in _merge(busy):
        next_result: list[Interval] = []
        for start, end in result:
            if busy_end <= start or busy_start >= end:
                next_result.append((start, end))
                continue
            if start < busy_start:
                next_result.append((start, busy_start))
            if busy_end < end:
                next_result.append((busy_end, end))
        result = next_result
    return result


def _rule_intervals(
    rules: list[AvailabilityRule],
    timezone: str,
    start: datetime,
    end: datetime,
) -> list[Interval]:
    zone = ZoneInfo(timezone)
    start_local = start.astimezone(zone)
    end_local = end.astimezone(zone)
    current = start_local.date()
    last = end_local.date()
    intervals: list[Interval] = []
    while current <= last:
        weekday = current.isoweekday()
        for rule in rules:
            if rule.weekday != weekday:
                continue
            if rule.valid_from is not None and current < rule.valid_from:
                continue
            if rule.valid_to is not None and current > rule.valid_to:
                continue
            local_start = datetime.combine(current, rule.start_time, tzinfo=zone)
            end_date = current
            if rule.end_time == time(0, 0):
                end_date = current + timedelta(days=1)
            local_end = datetime.combine(end_date, rule.end_time, tzinfo=zone)
            rule_start = max(local_start.astimezone(UTC), start)
            rule_end = min(local_end.astimezone(UTC), end)
            if rule_start < rule_end:
                intervals.append((rule_start, rule_end))
        current += timedelta(days=1)
    return _merge(intervals)


def _free_intervals(
    *,
    rules: list[AvailabilityRule],
    timezone: str,
    busy: list[Interval],
    start: datetime,
    end: datetime,
) -> list[Interval]:
    return _subtract(_rule_intervals(rules, timezone, start, end), busy)


def _range_bounds(value: Any) -> Interval | None:
    lower = getattr(value, "lower", None)
    upper = getattr(value, "upper", None)
    if isinstance(lower, datetime) and isinstance(upper, datetime):
        return lower, upper
    return None


async def _busy_intervals(
    session: AsyncSession,
    resource_ids: list[UUID],
    start: datetime,
    end: datetime,
) -> list[Interval]:
    if not resource_ids:
        return []
    requested = func.tstzrange(start, end, "[)")
    intervals: list[Interval] = []
    block_rows: Any = await session.scalars(
        select(BlockedInterval.time_range).where(
            BlockedInterval.resource_id.in_(resource_ids),
            BlockedInterval.time_range.op("&&")(requested),
        )
    )
    for value in block_rows:
        bounds = _range_bounds(value)
        if bounds is not None:
            intervals.append(bounds)

    reservation_rows: Any = await session.scalars(
        select(Reservation.time_range).where(
            Reservation.resource_id.in_(resource_ids),
            Reservation.time_range.op("&&")(requested),
            (
                Reservation.status.in_(LIVE_RESERVATION_STATUSES)
                | (
                    (Reservation.status == "pending_confirmation")
                    & (Reservation.hold_expires_at > func.now())
                )
            ),
        )
    )
    for value in reservation_rows:
        bounds = _range_bounds(value)
        if bounds is not None:
            intervals.append(bounds)
    return intervals


async def _listing_resources(session: AsyncSession, listing_id: UUID) -> list[UUID]:
    return list(await session.scalars(select(Resource.id).where(Resource.listing_id == listing_id)))


async def get_public_availability(
    session: AsyncSession,
    listing_id: UUID,
    start: datetime,
    end: datetime,
) -> AvailabilityResponse:
    listing = await session.scalar(
        select(Listing).where(
            Listing.id == listing_id,
            Listing.status == ListingStatus.ACTIVE,
        )
    )
    if listing is None:
        raise AppError(ErrorCode.NOT_FOUND, "Listing not found.", status_code=404)
    rules = list(
        await session.scalars(
            select(AvailabilityRule)
            .where(AvailabilityRule.listing_id == listing.id)
            .order_by(AvailabilityRule.weekday, AvailabilityRule.start_time)
        )
    )
    resources = await _listing_resources(session, listing.id)
    busy = await _busy_intervals(session, resources, start, end)
    windows = _free_intervals(
        rules=rules,
        timezone=listing.timezone,
        busy=busy,
        start=start,
        end=end,
    )
    return AvailabilityResponse(
        listing_id=listing.id,
        timezone=listing.timezone,
        from_=start,
        to=end,
        windows=[
            AvailabilityWindow(start=window_start, end=window_end)
            for window_start, window_end in windows
        ],
    )


async def available_listing_ids(
    session: AsyncSession,
    listing_ids: list[UUID],
    start: datetime,
    end: datetime,
) -> set[UUID]:
    if not listing_ids:
        return set()
    listings = {
        listing.id: listing
        for listing in await session.scalars(select(Listing).where(Listing.id.in_(listing_ids)))
    }
    rules_by_listing: dict[UUID, list[AvailabilityRule]] = defaultdict(list)
    for rule in await session.scalars(
        select(AvailabilityRule).where(AvailabilityRule.listing_id.in_(listing_ids))
    ):
        rules_by_listing[rule.listing_id].append(rule)
    resources: dict[UUID, list[UUID]] = defaultdict(list)
    for resource in await session.scalars(
        select(Resource).where(Resource.listing_id.in_(listing_ids))
    ):
        resources[resource.listing_id].append(resource.id)
    resource_to_listing = {
        resource_id: listing_id
        for listing_id, resource_ids in resources.items()
        for resource_id in resource_ids
    }
    busy_by_listing: dict[UUID, list[Interval]] = defaultdict(list)
    all_resources = list(resource_to_listing)
    if all_resources:
        requested = func.tstzrange(start, end, "[)")
        block_rows = await session.execute(
            select(BlockedInterval.resource_id, BlockedInterval.time_range).where(
                BlockedInterval.resource_id.in_(all_resources),
                BlockedInterval.time_range.op("&&")(requested),
            )
        )
        for raw_resource_id, value in block_rows:
            bounds = _range_bounds(value)
            if bounds is not None:
                resource_id = type_cast(UUID, raw_resource_id)
                busy_by_listing[resource_to_listing[resource_id]].append(bounds)
        reservation_rows = await session.execute(
            select(Reservation.resource_id, Reservation.time_range).where(
                Reservation.resource_id.in_(all_resources),
                Reservation.time_range.op("&&")(requested),
                (
                    Reservation.status.in_(LIVE_RESERVATION_STATUSES)
                    | (
                        (Reservation.status == "pending_confirmation")
                        & (Reservation.hold_expires_at > func.now())
                    )
                ),
            )
        )
        for raw_resource_id, value in reservation_rows:
            bounds = _range_bounds(value)
            if bounds is not None:
                resource_id = type_cast(UUID, raw_resource_id)
                busy_by_listing[resource_to_listing[resource_id]].append(bounds)

    available: set[UUID] = set()
    for listing_id in listing_ids:
        listing = listings.get(listing_id)
        if listing is None:
            continue
        windows = _free_intervals(
            rules=rules_by_listing[listing_id],
            timezone=listing.timezone,
            busy=busy_by_listing[listing_id],
            start=start,
            end=end,
        )
        if windows:
            available.add(listing_id)
    return available


async def _get_owner_listing(
    session: AsyncSession,
    user: User,
    listing_id: UUID,
) -> Listing:
    listing = await session.scalar(
        select(Listing).where(Listing.id == listing_id, Listing.owner_id == user.id)
    )
    if listing is None:
        raise AppError(ErrorCode.NOT_FOUND, "Listing not found.", status_code=404)
    return listing


async def list_rules(
    session: AsyncSession,
    user: User,
    listing_id: UUID,
) -> list[AvailabilityRuleRead]:
    listing = await _get_owner_listing(session, user, listing_id)
    rules = await session.scalars(
        select(AvailabilityRule)
        .where(AvailabilityRule.listing_id == listing.id)
        .order_by(AvailabilityRule.weekday, AvailabilityRule.start_time)
    )
    return [_rule_read(rule) for rule in rules]


def _rule_read(rule: AvailabilityRule) -> AvailabilityRuleRead:
    return AvailabilityRuleRead(
        id=rule.id,
        weekday=rule.weekday,
        start_time=rule.start_time,
        end_time=rule.end_time,
        valid_from=rule.valid_from,
        valid_to=rule.valid_to,
    )


async def replace_rules(
    session: AsyncSession,
    user: User,
    listing_id: UUID,
    payload: AvailabilityRulesPayload,
) -> list[AvailabilityRuleRead]:
    listing = await _get_owner_listing(session, user, listing_id)
    _validate_rule_overlaps(payload.rules)
    existing = list(
        await session.scalars(
            select(AvailabilityRule).where(AvailabilityRule.listing_id == listing.id)
        )
    )
    before = {"rules": [_rule_read(rule).model_dump(mode="json") for rule in existing]}
    for rule in existing:
        await session.delete(rule)
    for new_rule in payload.rules:
        session.add(
            AvailabilityRule(
                listing_id=listing.id,
                weekday=new_rule.weekday,
                start_time=new_rule.start_time,
                end_time=new_rule.end_time,
                valid_from=new_rule.valid_from,
                valid_to=new_rule.valid_to,
            )
        )
    record_event(
        session,
        actor=user,
        action="listing.availability_rules_replaced",
        entity_type="listing",
        entity_id=listing.id,
        before=before,
        after={"rules": [new_rule.fingerprint() for new_rule in payload.rules]},
    )
    await session.commit()
    return await list_rules(session, user, listing.id)


async def _default_resource(session: AsyncSession, listing_id: UUID) -> Resource:
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


async def _live_reservation_conflicts(
    session: AsyncSession,
    resource_id: UUID,
    start: datetime,
    end: datetime,
) -> list[str]:
    requested = func.tstzrange(start, end, "[)")
    return list(
        await session.scalars(
            select(Reservation.reference).where(
                Reservation.resource_id == resource_id,
                Reservation.time_range.op("&&")(requested),
                (
                    Reservation.status.in_(LIVE_RESERVATION_STATUSES)
                    | (
                        (Reservation.status == "pending_confirmation")
                        & (Reservation.hold_expires_at > func.now())
                    )
                ),
            )
        )
    )


async def create_block(
    session: AsyncSession,
    user: User,
    listing_id: UUID,
    payload: BlockCreate,
) -> BlockRead:
    listing = await _get_owner_listing(session, user, listing_id)
    resource = await _default_resource(session, listing.id)
    conflicts = await _live_reservation_conflicts(session, resource.id, payload.start, payload.end)
    if conflicts:
        raise AppError(
            ErrorCode.BLOCK_CONFLICTS_BOOKING,
            "Block conflicts with an existing booking.",
            status_code=409,
            details=[
                {"field": "start", "message": f"Reservation {reference}", "type": "conflict"}
                for reference in conflicts
            ],
        )
    block = BlockedInterval(
        resource_id=resource.id,
        time_range=func.tstzrange(payload.start, payload.end, "[)"),
        reason=payload.reason,
        created_by=user.id,
    )
    session.add(block)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            ErrorCode.SLOT_UNAVAILABLE,
            "Blocked interval overlaps an existing block.",
            status_code=409,
        ) from exc
    record_event(
        session,
        actor=user,
        action="listing.block_created",
        entity_type="listing",
        entity_id=listing.id,
        after={
            "block_id": str(block.id),
            "start": payload.start.isoformat(),
            "end": payload.end.isoformat(),
            "reason": payload.reason,
        },
    )
    await session.commit()
    await session.refresh(block)
    return _block_read(block)


async def list_blocks(
    session: AsyncSession,
    user: User,
    listing_id: UUID,
) -> list[BlockRead]:
    listing = await _get_owner_listing(session, user, listing_id)
    blocks = await session.execute(
        select(BlockedInterval)
        .join(Resource, Resource.id == BlockedInterval.resource_id)
        .where(Resource.listing_id == listing.id)
        .order_by(BlockedInterval.time_range)
    )
    return [_block_read(block) for block in blocks.scalars()]


def _block_read(block: BlockedInterval) -> BlockRead:
    bounds = _range_bounds(block.time_range)
    if bounds is None:
        raise RuntimeError("Blocked interval has no bounds")
    return BlockRead(
        id=block.id,
        start=bounds[0],
        end=bounds[1],
        reason=block.reason,
        created_at=block.created_at,
    )


async def delete_block(
    session: AsyncSession,
    user: User,
    listing_id: UUID,
    block_id: UUID,
) -> None:
    listing = await _get_owner_listing(session, user, listing_id)
    block = await session.scalar(
        select(BlockedInterval)
        .join(Resource, Resource.id == BlockedInterval.resource_id)
        .where(
            BlockedInterval.id == block_id,
            Resource.listing_id == listing.id,
        )
        .with_for_update()
    )
    if block is None:
        raise AppError(ErrorCode.NOT_FOUND, "Block not found.", status_code=404)
    before = _block_read(block).model_dump(mode="json")
    await session.delete(block)
    record_event(
        session,
        actor=user,
        action="listing.block_deleted",
        entity_type="listing",
        entity_id=listing.id,
        before=before,
    )
    await session.commit()


async def is_listing_window_available(
    session: AsyncSession,
    listing: Listing,
    start: datetime,
    end: datetime,
) -> bool:
    """Return whether a listing's rules fully cover a requested window.

    Existing reservations and blocks are treated as busy. The caller should
    hold the resource row lock before using this check for a write.
    """
    rules = list(
        await session.scalars(
            select(AvailabilityRule)
            .where(AvailabilityRule.listing_id == listing.id)
            .order_by(AvailabilityRule.weekday, AvailabilityRule.start_time)
        )
    )
    resources = await _listing_resources(session, listing.id)
    busy = await _busy_intervals(session, resources, start, end)
    windows = _free_intervals(
        rules=rules,
        timezone=listing.timezone,
        busy=busy,
        start=start,
        end=end,
    )
    return any(window_start <= start and end <= window_end for window_start, window_end in windows)
