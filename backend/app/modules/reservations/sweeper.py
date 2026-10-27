"""Single-instance reservation sweeper using PostgreSQL advisory locks."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.reservations.models import IdempotencyKey
from app.modules.reservations.service import reconcile_all

SWEEPER_LOCK_KEY = 0x53544841
_logger = structlog.get_logger("sthalo.sweeper")


async def sweep_once(session: AsyncSession) -> dict[str, Any]:
    """Reconcile due states and clean expired idempotency keys once."""
    acquired = await session.scalar(select(func.pg_try_advisory_lock(SWEEPER_LOCK_KEY)))
    if not acquired:
        return {"skipped": True, "reconciled": False, "idempotency_keys_deleted": 0}
    deleted = 0
    reconciled = False
    try:
        reconciled = await reconcile_all(session)
        result = await session.execute(
            delete(IdempotencyKey)
            .where(IdempotencyKey.expires_at <= func.now())
            .returning(IdempotencyKey.id)
        )
        deleted = len(result.all())
        await session.commit()
        if reconciled or deleted:
            _logger.info(
                "reservation_sweep_completed",
                reconciled=reconciled,
                idempotency_keys_deleted=deleted,
            )
        return {
            "skipped": False,
            "reconciled": reconciled,
            "idempotency_keys_deleted": deleted,
        }
    except Exception:
        await session.rollback()
        raise
    finally:
        with suppress(Exception):
            await session.scalar(select(func.pg_advisory_unlock(SWEEPER_LOCK_KEY)))


async def run_sweeper(
    session_factory: async_sessionmaker[AsyncSession],
    interval_seconds: int,
    stop_event: asyncio.Event,
) -> None:
    """Run periodic sweeps until the application shuts down."""
    while not stop_event.is_set():
        try:
            if await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds):
                break
        except TimeoutError:
            pass
        try:
            async with session_factory() as session:
                await sweep_once(session)
        except asyncio.CancelledError:
            raise
        except Exception:
            _logger.exception("reservation_sweep_failed")


def start_sweeper(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    interval_seconds: int,
) -> tuple[asyncio.Task[None], asyncio.Event]:
    stop_event = asyncio.Event()
    task = asyncio.create_task(
        run_sweeper(session_factory, interval_seconds, stop_event),
        name="reservation-sweeper",
    )
    return task, stop_event
