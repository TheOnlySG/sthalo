"""Idempotency-key claim, replay, and response storage."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.modules.identity.models import User
from app.modules.reservations.models import IdempotencyKey

IDEMPOTENCY_TTL = timedelta(hours=24)
MAX_KEY_LENGTH = 128


@dataclass
class IdempotencyClaim:
    row: IdempotencyKey
    replay: dict[str, Any] | None
    replay_status: int | None


def request_fingerprint(operation: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        {"operation": operation, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def claim_idempotency(
    session: AsyncSession,
    *,
    user: User,
    key: str,
    fingerprint: str,
) -> IdempotencyClaim:
    cleaned = key.strip()
    if not cleaned or len(cleaned) > MAX_KEY_LENGTH:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Idempotency-Key must contain between 1 and 128 characters.",
            status_code=422,
            details=[
                {
                    "field": "Idempotency-Key",
                    "message": "Provide a non-empty key of at most 128 characters.",
                    "type": "value_error",
                }
            ],
        )

    statement = (
        insert(IdempotencyKey)
        .values(
            user_id=user.id,
            key=cleaned,
            request_hash=fingerprint,
            expires_at=func.now() + text("interval '24 hours'"),
        )
        .on_conflict_do_nothing(index_elements=["user_id", "key"])
    )
    await session.execute(statement)
    row = await session.scalar(
        select(IdempotencyKey)
        .where(IdempotencyKey.user_id == user.id, IdempotencyKey.key == cleaned)
        .with_for_update()
    )
    if row is None:
        raise RuntimeError("Idempotency key could not be claimed")

    now = await session.scalar(select(func.now()))
    if not isinstance(now, datetime):
        raise RuntimeError("Database clock is unavailable")

    if row.expires_at <= now:
        row.request_hash = fingerprint
        row.response_status = None
        row.response_body = None
        row.created_at = now
        row.expires_at = now + IDEMPOTENCY_TTL
        await session.flush()
    elif row.request_hash != fingerprint:
        raise AppError(
            ErrorCode.IDEMPOTENCY_KEY_REUSED,
            "This Idempotency-Key was already used with a different request.",
            status_code=409,
        )

    if row.response_body is not None and row.response_status is not None:
        return IdempotencyClaim(
            row=row,
            replay=row.response_body,
            replay_status=row.response_status,
        )
    return IdempotencyClaim(row=row, replay=None, replay_status=None)


async def store_idempotency_response(
    session: AsyncSession,
    row: IdempotencyKey,
    *,
    status_code: int,
    body: dict[str, Any],
) -> None:
    row.response_status = status_code
    row.response_body = body
    now = await session.scalar(select(func.now()))
    if isinstance(now, datetime):
        row.expires_at = now + IDEMPOTENCY_TTL


async def discard_idempotency(session: AsyncSession, row: IdempotencyKey) -> None:
    await session.delete(row)
