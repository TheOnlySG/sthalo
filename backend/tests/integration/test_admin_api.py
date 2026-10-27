"""Database-backed V7 admin read-only API tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from tests.integration.conftest import TestUser
from tests.integration.test_listings_api import BASE, _headers
from tests.integration.test_reservations_api import _create, _setup


def test_admin_overview_reservations_and_audit_timeline(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    context = _setup(client, auth_user_factory, token_for, db_execute)
    created = _create(client, context)
    assert created.status_code == 201, created.text
    reservation_id = created.json()["id"]

    confirmed = client.post(
        f"{BASE}/reservations/{reservation_id}/confirm",
        headers={**_headers(context["customer_token"]), "Idempotency-Key": str(uuid4())},
    )
    assert confirmed.status_code == 200, confirmed.text

    overview = client.get(f"{BASE}/admin/overview", headers=_headers(context["admin_token"]))
    assert overview.status_code == 200, overview.text
    counts = overview.json()
    assert counts["live_reservations"] == 1
    assert counts["expiring_holds"] == 0
    assert counts["pending_listings"] == 0

    listed = client.get(
        f"{BASE}/admin/reservations",
        headers=_headers(context["admin_token"]),
        params={"status": "confirmed"},
    )
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [reservation_id]
    assert listed.json()[0]["exact_address"] == "123 12th Main Road"
    assert listed.json()[0]["customer_name"] == "Customer Person"

    detail = client.get(
        f"{BASE}/admin/reservations/{reservation_id}",
        headers=_headers(context["admin_token"]),
    )
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["reservation"]["status"] == "confirmed"
    assert [event["action"] for event in body["audit"]] == [
        "reservation.confirmed",
        "reservation.created",
    ]

    audit = client.get(
        f"{BASE}/admin/audit",
        headers=_headers(context["admin_token"]),
        params={"entity_type": "reservation", "entity_id": reservation_id},
    )
    assert audit.status_code == 200
    assert len(audit.json()) == 2
    assert audit.json()[0]["actor_email"] == context["customer"].email

    future = datetime.now(UTC) + timedelta(days=1)
    empty = client.get(
        f"{BASE}/admin/audit",
        headers=_headers(context["admin_token"]),
        params={"entity_type": "reservation", "from": future.isoformat()},
    )
    assert empty.status_code == 200
    assert empty.json() == []

    naive = client.get(
        f"{BASE}/admin/audit",
        headers=_headers(context["admin_token"]),
        params={"from": "2026-01-01T00:00:00"},
    )
    assert naive.status_code == 422


def test_non_admin_cannot_read_admin_endpoints(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    context = _setup(client, auth_user_factory, token_for, db_execute)
    created = _create(client, context)
    assert created.status_code == 201

    for path in (
        "/admin/overview",
        "/admin/reservations",
        f"/admin/reservations/{created.json()['id']}",
        "/admin/audit",
    ):
        response = client.get(f"{BASE}{path}", headers=_headers(context["customer_token"]))
        assert response.status_code == 403, (path, response.text)

    missing = client.get(
        f"{BASE}/admin/reservations",
        headers=_headers(context["customer_token"]),
    )
    assert missing.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_filter_reservations_by_listing(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    context = _setup(client, auth_user_factory, token_for, db_execute)
    created = _create(client, context)
    assert created.status_code == 201

    matching = client.get(
        f"{BASE}/admin/reservations",
        headers=_headers(context["admin_token"]),
        params={"listing_id": context["listing"]["id"]},
    )
    assert matching.status_code == 200
    assert [item["id"] for item in matching.json()] == [created.json()["id"]]

    missing = client.get(
        f"{BASE}/admin/reservations",
        headers=_headers(context["admin_token"]),
        params={"listing_id": str(uuid4())},
    )
    assert missing.status_code == 200
    assert missing.json() == []
