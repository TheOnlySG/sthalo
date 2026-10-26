"""Database-backed V4 availability rule and block tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from tests.integration.conftest import TestUser
from tests.integration.test_listings_api import (
    BASE,
    _accept_terms,
    _headers,
    _make_admin,
)
from tests.integration.test_search_api import _nearby_listing, _parking

MONDAY = datetime(2026, 11, 2, tzinfo=UTC)
WINDOW_START = MONDAY.replace(hour=3, minute=30)
WINDOW_END = MONDAY.replace(hour=12, minute=30)


def _active_listing(
    client: TestClient,
    token: str,
    admin_token: str,
) -> dict[str, Any]:
    return _nearby_listing(
        client,
        token,
        admin_token,
        title="Availability test bay",
        latitude=19.9975,
        longitude=73.7898,
        parking=_parking(),
    )


def _rules(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rules": [
            {"weekday": 1, "start_time": "09:00:00", "end_time": "12:00:00"},
            {"weekday": 1, "start_time": "13:00:00", "end_time": "18:00:00"},
        ]
    }
    payload.update(overrides)
    return payload


def _put_rules(
    client: TestClient,
    token: str,
    listing_id: str,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    response = client.put(
        f"{BASE}/owner/parking-listings/{listing_id}/availability-rules",
        headers=_headers(token),
        json=payload,
    )
    assert response.status_code == 200, response.text
    rules: list[dict[str, Any]] = response.json()
    return rules


def _availability(
    client: TestClient,
    listing_id: str,
    start: datetime = WINDOW_START,
    end: datetime = WINDOW_END,
) -> list[tuple[datetime, datetime]]:
    response = client.get(
        f"{BASE}/parking-listings/{listing_id}/availability",
        params={"from": start.isoformat(), "to": end.isoformat()},
    )
    assert response.status_code == 200, response.text
    return [
        (datetime.fromisoformat(item["start"]), datetime.fromisoformat(item["end"]))
        for item in response.json()["windows"]
    ]


def test_owner_can_replace_rules_and_public_availability_uses_them(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    admin = _make_admin(db_execute, auth_user_factory)
    listing = _active_listing(client, token, token_for(admin))

    rules = _put_rules(client, token, listing["id"], _rules())

    assert [rule["weekday"] for rule in rules] == [1, 1]
    assert _availability(client, listing["id"]) == [
        (
            datetime(2026, 11, 2, 3, 30, tzinfo=UTC),
            datetime(2026, 11, 2, 6, 30, tzinfo=UTC),
        ),
        (
            datetime(2026, 11, 2, 7, 30, tzinfo=UTC),
            datetime(2026, 11, 2, 12, 30, tzinfo=UTC),
        ),
    ]


def test_block_splits_availability_and_can_be_deleted(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    admin = _make_admin(db_execute, auth_user_factory)
    listing = _active_listing(client, token, token_for(admin))
    _put_rules(client, token, listing["id"], _rules())

    block_response = client.post(
        f"{BASE}/owner/parking-listings/{listing['id']}/blocks",
        headers=_headers(token),
        json={
            "start": MONDAY.replace(hour=4, minute=30).isoformat(),
            "end": MONDAY.replace(hour=5, minute=30).isoformat(),
            "reason": "Personal use",
        },
    )
    assert block_response.status_code == 201, block_response.text
    block = block_response.json()
    assert block["reason"] == "Personal use"

    windows = _availability(client, listing["id"])
    assert windows == [
        (
            datetime(2026, 11, 2, 3, 30, tzinfo=UTC),
            datetime(2026, 11, 2, 4, 30, tzinfo=UTC),
        ),
        (
            datetime(2026, 11, 2, 5, 30, tzinfo=UTC),
            datetime(2026, 11, 2, 6, 30, tzinfo=UTC),
        ),
        (
            datetime(2026, 11, 2, 7, 30, tzinfo=UTC),
            datetime(2026, 11, 2, 12, 30, tzinfo=UTC),
        ),
    ]

    overlapping = client.post(
        f"{BASE}/owner/parking-listings/{listing['id']}/blocks",
        headers=_headers(token),
        json={
            "start": MONDAY.replace(hour=4, minute=45).isoformat(),
            "end": MONDAY.replace(hour=5, minute=15).isoformat(),
        },
    )
    assert overlapping.status_code == 409
    assert overlapping.json()["error"]["code"] == "SLOT_UNAVAILABLE"

    listed = client.get(
        f"{BASE}/owner/parking-listings/{listing['id']}/blocks",
        headers=_headers(token),
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [block["id"]]

    deleted = client.delete(
        f"{BASE}/owner/parking-listings/{listing['id']}/blocks/{block['id']}",
        headers=_headers(token),
    )
    assert deleted.status_code == 204
    assert len(_availability(client, listing["id"])) == 2


def test_overlapping_rules_are_rejected(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    admin = _make_admin(db_execute, auth_user_factory)
    listing = _active_listing(client, token, token_for(admin))

    response = client.put(
        f"{BASE}/owner/parking-listings/{listing['id']}/availability-rules",
        headers=_headers(token),
        json={
            "rules": [
                {"weekday": 1, "start_time": "09:00:00", "end_time": "12:00:00"},
                {"weekday": 1, "start_time": "11:45:00", "end_time": "14:00:00"},
            ]
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_non_owner_cannot_manage_rules(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    admin = _make_admin(db_execute, auth_user_factory)
    listing = _active_listing(client, token, token_for(admin))
    other = auth_user_factory()
    other_token = token_for(other)

    response = client.put(
        f"{BASE}/owner/parking-listings/{listing['id']}/availability-rules",
        headers=_headers(other_token),
        json=_rules(),
    )

    assert response.status_code == 404


def test_block_conflicts_with_confirmed_reservation(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
    db_fetchval: Callable[..., object],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    admin = _make_admin(db_execute, auth_user_factory)
    listing = _active_listing(client, token, token_for(admin))
    resource_id = UUID(
        str(
            db_fetchval(
                "SELECT id FROM sthalo.resources WHERE listing_id = $1",
                UUID(listing["id"]),
            )
        )
    )
    vehicle_id = UUID(
        str(
            db_fetchval(
                "INSERT INTO sthalo.vehicles (user_id, vehicle_type) "
                "VALUES ($1, 'sedan') RETURNING id",
                owner.id,
            )
        )
    )
    db_execute(
        """
        INSERT INTO sthalo.reservations (
            reference, customer_id, owner_id, listing_id, resource_id, vehicle_id,
            time_range, status, base_amount_paise, total_paise, price_snapshot,
            confirmed_at
        ) VALUES (
            $1, $2, $2, $3, $4, $5, tstzrange($6, $7, '[)'),
            'confirmed', 0, 0, '{}'::jsonb, now()
        )
        """,
        f"TEST-{owner.id}",
        owner.id,
        UUID(listing["id"]),
        resource_id,
        vehicle_id,
        MONDAY.replace(hour=4, minute=0),
        MONDAY.replace(hour=5, minute=0),
    )

    response = client.post(
        f"{BASE}/owner/parking-listings/{listing['id']}/blocks",
        headers=_headers(token),
        json={
            "start": MONDAY.replace(hour=4, minute=30).isoformat(),
            "end": MONDAY.replace(hour=5, minute=30).isoformat(),
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "BLOCK_CONFLICTS_BOOKING"


def test_availability_rejects_unaligned_and_excessive_windows(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    admin = _make_admin(db_execute, auth_user_factory)
    listing = _active_listing(client, token, token_for(admin))

    unaligned = client.get(
        f"{BASE}/parking-listings/{listing['id']}/availability",
        params={
            "from": MONDAY.replace(hour=3, minute=37).isoformat(),
            "to": WINDOW_END.isoformat(),
        },
    )
    excessive = client.get(
        f"{BASE}/parking-listings/{listing['id']}/availability",
        params={
            "from": MONDAY.isoformat(),
            "to": MONDAY.replace(month=12, day=4).isoformat(),
        },
    )

    assert unaligned.status_code == 422
    assert excessive.status_code == 422
