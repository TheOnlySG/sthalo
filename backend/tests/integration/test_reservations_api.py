"""Database-backed V5 reservation lifecycle and concurrency tests."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tests.integration.conftest import TestUser
from tests.integration.test_listings_api import (
    BASE,
    _accept_terms,
    _headers,
    _make_admin,
)
from tests.integration.test_search_api import _nearby_listing, _parking

from app.modules.reservations.sweeper import sweep_once

INDIA = ZoneInfo("Asia/Kolkata")


def _future_window() -> tuple[datetime, datetime, int]:
    target = datetime.now(UTC).astimezone(INDIA).date() + timedelta(days=7)
    start = datetime.combine(target, time(9, 0), tzinfo=INDIA).astimezone(UTC)
    end = datetime.combine(target, time(18, 0), tzinfo=INDIA).astimezone(UTC)
    return start, end, target.isoweekday()


def _create_vehicle(
    client: TestClient,
    token: str,
    *,
    vehicle_type: str = "hatchback",
) -> dict[str, Any]:
    response = client.post(
        f"{BASE}/vehicles",
        headers=_headers(token),
        json={
            "vehicle_type": vehicle_type,
            "registration_no": "MH15AB1234",
            "length_mm": 4000,
            "width_mm": 1800,
            "height_mm": 1600,
        },
    )
    assert response.status_code == 201, response.text
    vehicle: dict[str, Any] = response.json()
    return vehicle


def _set_all_week_rules(
    client: TestClient,
    token: str,
    listing_id: str,
    *,
    start: str = "09:00:00",
    end: str = "18:00:00",
) -> None:
    response = client.put(
        f"{BASE}/owner/parking-listings/{listing_id}/availability-rules",
        headers=_headers(token),
        json={
            "rules": [
                {"weekday": weekday, "start_time": start, "end_time": end}
                for weekday in range(1, 8)
            ]
        },
    )
    assert response.status_code == 200, response.text


def _setup(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
    *,
    parking: dict[str, Any] | None = None,
) -> dict[str, Any]:
    owner = auth_user_factory(full_name="Owner Person")
    owner_token = token_for(owner)
    _accept_terms(client, owner_token)
    admin = _make_admin(db_execute, auth_user_factory)
    listing = _nearby_listing(
        client,
        owner_token,
        token_for(admin),
        title="Reservation test bay",
        latitude=19.9975,
        longitude=73.7898,
        parking=parking or _parking(),
    )
    _set_all_week_rules(client, owner_token, listing["id"])

    customer = auth_user_factory(full_name="Customer Person")
    customer_token = token_for(customer)
    vehicle = _create_vehicle(client, customer_token)
    start, end, _weekday = _future_window()
    return {
        "owner": owner,
        "owner_token": owner_token,
        "admin": admin,
        "admin_token": token_for(admin),
        "customer": customer,
        "customer_token": customer_token,
        "listing": listing,
        "vehicle": vehicle,
        "start": start,
        "end": end,
    }


def _payload(context: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "listing_id": context["listing"]["id"],
        "vehicle_id": context["vehicle"]["id"],
        "start": context["start"].isoformat(),
        "end": context["end"].isoformat(),
    }
    payload.update(overrides)
    return payload


def _create(
    client: TestClient,
    context: dict[str, Any],
    *,
    key: str | None = None,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    return client.post(
        f"{BASE}/reservations",
        headers={
            **_headers(token or context["customer_token"]),
            "Idempotency-Key": key or str(uuid4()),
        },
        json=payload or _payload(context),
    )


def _quote(
    client: TestClient,
    context: dict[str, Any],
    *,
    end: datetime | None = None,
) -> dict[str, Any]:
    response = client.post(
        f"{BASE}/reservations/quote",
        headers=_headers(context["customer_token"]),
        json=_payload(context, end=(end or context["end"]).isoformat()),
    )
    assert response.status_code == 200, response.text
    quote: dict[str, Any] = response.json()
    return quote


def test_quote_returns_authoritative_breakdown_without_writing(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
    db_fetchval: Callable[..., object],
) -> None:
    context = _setup(client, auth_user_factory, token_for, db_execute)
    end = context["start"] + timedelta(minutes=135)

    quote = _quote(client, context, end=end)

    assert quote["total_paise"] == 11_250
    assert quote["price"]["duration_minutes"] == 135
    assert quote["price"]["billable_minutes"] == 135
    assert quote["price"]["hourly_component_paise"] == 11_250
    assert quote["price"]["cap_component_paise"] == 30_000
    assert (
        db_fetchval(
            "SELECT count(*) FROM sthalo.reservations WHERE listing_id = $1",
            UUID(context["listing"]["id"]),
        )
        == 0
    )


def test_hold_confirm_privacy_and_list(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    context = _setup(client, auth_user_factory, token_for, db_execute)
    created = _create(client, context)
    assert created.status_code == 201, created.text
    reservation = created.json()
    assert reservation["status"] == "pending_confirmation"
    assert reservation["exact_address"] is None
    assert reservation["access_instructions"] is None
    assert reservation["can_confirm"] is True
    assert reservation["hold_expires_at"] is not None

    detail = client.get(
        f"{BASE}/reservations/{reservation['id']}",
        headers=_headers(context["customer_token"]),
    )
    assert detail.status_code == 200
    assert detail.json()["viewer_role"] == "customer"
    assert detail.json()["exact_address"] is None

    owner_detail = client.get(
        f"{BASE}/reservations/{reservation['id']}",
        headers=_headers(context["owner_token"]),
    )
    assert owner_detail.status_code == 200
    assert owner_detail.json()["customer_name"] == "Customer Person"
    assert owner_detail.json()["vehicle"]["registration_no"] == "MH15AB1234"

    confirm = client.post(
        f"{BASE}/reservations/{reservation['id']}/confirm",
        headers={**_headers(context["customer_token"]), "Idempotency-Key": str(uuid4())},
    )
    assert confirm.status_code == 200, confirm.text
    confirmed = confirm.json()
    assert confirmed["status"] == "confirmed"
    assert confirmed["exact_address"] == "123 12th Main Road"
    assert confirmed["access_instructions"] == "Use gate code 4455 and park in bay two."
    assert confirmed["confirmed_at"] is not None

    repeat = client.post(
        f"{BASE}/reservations/{reservation['id']}/confirm",
        headers={**_headers(context["customer_token"]), "Idempotency-Key": str(uuid4())},
    )
    assert repeat.status_code == 200
    assert repeat.json()["id"] == reservation["id"]
    assert repeat.json()["status"] == "confirmed"

    mine = client.get(f"{BASE}/reservations/me", headers=_headers(context["customer_token"]))
    assert mine.status_code == 200
    assert [item["id"] for item in mine.json()] == [reservation["id"]]

    owner_list = client.get(f"{BASE}/owner/reservations", headers=_headers(context["owner_token"]))
    assert owner_list.status_code == 200
    assert owner_list.json()[0]["customer_name"] == "Customer Person"


def test_create_idempotency_replays_and_rejects_different_payload(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    context = _setup(client, auth_user_factory, token_for, db_execute)
    key = f"create-{uuid4()}"

    first = _create(client, context, key=key)
    second = _create(client, context, key=key)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    conflict = _create(
        client,
        context,
        key=key,
        payload=_payload(context, end=(context["end"] + timedelta(minutes=15)).isoformat()),
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_expired_hold_is_released_and_confirm_returns_hold_expired(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    context = _setup(client, auth_user_factory, token_for, db_execute)
    created = _create(client, context)
    assert created.status_code == 201, created.text
    reservation = created.json()
    db_execute(
        "UPDATE sthalo.reservations SET hold_expires_at = now() - interval '1 minute' "
        "WHERE id = $1",
        UUID(reservation["id"]),
    )

    expired = client.post(
        f"{BASE}/reservations/{reservation['id']}/confirm",
        headers={**_headers(context["customer_token"]), "Idempotency-Key": str(uuid4())},
    )
    assert expired.status_code == 409
    assert expired.json()["error"]["code"] == "HOLD_EXPIRED"

    replacement = _create(client, context)
    assert replacement.status_code == 201, replacement.text
    assert replacement.json()["id"] != reservation["id"]


def test_sweeper_expires_holds_and_lazily_reconciles_states(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
    db_fetchval: Callable[..., object],
) -> None:
    context = _setup(client, auth_user_factory, token_for, db_execute)
    created = _create(client, context)
    assert created.status_code == 201, created.text
    reservation_id = UUID(created.json()["id"])
    db_execute(
        "UPDATE sthalo.reservations SET hold_expires_at = now() - interval '1 minute' "
        "WHERE id = $1",
        reservation_id,
    )

    async def run_sweep() -> dict[str, Any]:
        engine = create_async_engine(os.environ["DATABASE_URL"])
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        try:
            async with factory() as session:
                return await sweep_once(session)
        finally:
            await engine.dispose()

    result = asyncio.run(run_sweep())
    assert result["reconciled"] is True
    assert (
        db_fetchval(
            "SELECT status FROM sthalo.reservations WHERE id = $1",
            reservation_id,
        )
        == "expired"
    )

    confirmed = _create(client, context)
    assert confirmed.status_code == 201
    confirmed_id = UUID(confirmed.json()["id"])
    client.post(
        f"{BASE}/reservations/{confirmed_id}/confirm",
        headers={**_headers(context["customer_token"]), "Idempotency-Key": str(uuid4())},
    )
    now = datetime.now(UTC)
    db_execute(
        "UPDATE sthalo.reservations SET status = 'confirmed', confirmed_at = now(), "
        "time_range = tstzrange($1, $2, '[)') WHERE id = $3",
        now - timedelta(minutes=10),
        now + timedelta(minutes=20),
        confirmed_id,
    )
    active = client.get(
        f"{BASE}/reservations/{confirmed_id}",
        headers=_headers(context["customer_token"]),
    )
    assert active.status_code == 200
    assert active.json()["status"] == "active"

    db_execute(
        "UPDATE sthalo.reservations SET time_range = tstzrange($1, $2, '[)') WHERE id = $3",
        now - timedelta(hours=2),
        now - timedelta(hours=1),
        confirmed_id,
    )
    completed = client.get(
        f"{BASE}/reservations/{confirmed_id}",
        headers=_headers(context["customer_token"]),
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"


def test_owner_cancel_requires_reason_and_block_conflicts_with_booking(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    context = _setup(client, auth_user_factory, token_for, db_execute)
    created = _create(client, context)
    assert created.status_code == 201, created.text
    reservation = created.json()

    missing_reason = client.post(
        f"{BASE}/reservations/{reservation['id']}/cancel",
        headers={**_headers(context["owner_token"]), "Idempotency-Key": str(uuid4())},
        json={},
    )
    assert missing_reason.status_code == 422

    blocked = client.post(
        f"{BASE}/owner/parking-listings/{context['listing']['id']}/blocks",
        headers=_headers(context["owner_token"]),
        json={
            "start": context["start"].isoformat(),
            "end": context["end"].isoformat(),
            "reason": "Owner maintenance",
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "BLOCK_CONFLICTS_BOOKING"

    cancel = client.post(
        f"{BASE}/reservations/{reservation['id']}/cancel",
        headers={**_headers(context["owner_token"]), "Idempotency-Key": str(uuid4())},
        json={"reason": "Plumbing repair"},
    )
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "cancelled"
    assert cancel.json()["cancel_reason"] == "Plumbing repair"

    second = _create(client, context)
    assert second.status_code == 201


def test_vehicle_with_future_reservation_cannot_be_deleted(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    context = _setup(client, auth_user_factory, token_for, db_execute)
    created = _create(client, context)
    assert created.status_code == 201

    response = client.delete(
        f"{BASE}/vehicles/{context['vehicle']['id']}",
        headers=_headers(context["customer_token"]),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "HAS_FUTURE_BOOKINGS"


def test_twenty_simultaneous_creates_allow_exactly_one_hold(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
    db_fetchval: Callable[..., object],
) -> None:
    context = _setup(client, auth_user_factory, token_for, db_execute)

    def create_one(_index: int) -> int:
        return int(_create(client, context).status_code)

    with ThreadPoolExecutor(max_workers=20) as executor:
        statuses = list(executor.map(create_one, range(20)))

    assert statuses.count(201) == 1
    assert statuses.count(409) == 19
    assert all(status in {201, 409} for status in statuses)
    assert (
        db_fetchval(
            "SELECT count(*) FROM sthalo.reservations "
            "WHERE resource_id = (SELECT id FROM sthalo.resources WHERE listing_id = $1) "
            "AND status IN ('pending_confirmation', 'confirmed', 'active')",
            UUID(context["listing"]["id"]),
        )
        == 1
    )


def test_same_key_concurrent_creates_return_one_reservation(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
    db_fetchval: Callable[..., object],
) -> None:
    context = _setup(client, auth_user_factory, token_for, db_execute)
    key = f"same-{uuid4()}"

    def create_one(_index: int) -> tuple[int, str | None]:
        response = _create(client, context, key=key)
        body = response.json()
        return response.status_code, body.get("id")

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(create_one, range(8)))

    ids = {reservation_id for _, reservation_id in results}
    assert all(status == 201 for status, _ in results), results
    assert len(ids) == 1
    assert (
        db_fetchval(
            "SELECT count(*) FROM sthalo.reservations WHERE customer_id = $1",
            context["customer"].id,
        )
        == 1
    )


def test_block_and_booking_race_leaves_no_overlap(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
    db_fetchval: Callable[..., object],
) -> None:
    context = _setup(client, auth_user_factory, token_for, db_execute)

    def create_booking() -> int:
        return int(_create(client, context).status_code)

    def create_block() -> int:
        response = client.post(
            f"{BASE}/owner/parking-listings/{context['listing']['id']}/blocks",
            headers=_headers(context["owner_token"]),
            json={
                "start": context["start"].isoformat(),
                "end": context["end"].isoformat(),
                "reason": "Race repair",
            },
        )
        return int(response.status_code)

    with ThreadPoolExecutor(max_workers=2) as executor:
        booking_status, block_status = list(
            executor.map(lambda fn: fn(), [create_booking, create_block])
        )

    assert (booking_status, block_status) in {(201, 409), (409, 201)}
    assert (
        db_fetchval(
            "SELECT count(*) FROM sthalo.reservations r "
            "JOIN sthalo.blocked_intervals b "
            "ON b.resource_id = r.resource_id AND b.time_range && r.time_range "
            "WHERE r.listing_id = $1 "
            "AND r.status IN ('pending_confirmation', 'confirmed', 'active')",
            UUID(context["listing"]["id"]),
        )
        == 0
    )
