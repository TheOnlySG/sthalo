"""Database-backed vehicle CRUD and ownership tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient


def auth_headers(token_for: Callable[..., str], user: Any) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for(user)}"}


def test_vehicle_crud_and_normalization(
    client: TestClient,
    auth_user_factory: Callable[..., Any],
    token_for: Callable[..., str],
) -> None:
    user = auth_user_factory()
    headers = auth_headers(token_for, user)

    created = client.post(
        "/api/v1/vehicles",
        headers=headers,
        json={
            "vehicle_type": "sedan",
            "registration_no": "mh 12 ab 1234",
            "length_mm": 4700,
            "width_mm": 1800,
            "height_mm": 1500,
            "is_ev": False,
        },
    )
    assert created.status_code == 201, created.text
    vehicle = created.json()
    assert vehicle["registration_no"] == "MH12AB1234"
    assert "user_id" not in vehicle

    listed = client.get("/api/v1/vehicles", headers=headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [vehicle["id"]]

    updated = client.patch(
        f"/api/v1/vehicles/{vehicle['id']}",
        headers=headers,
        json={"vehicle_type": "suv", "is_ev": True, "registration_no": None},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["vehicle_type"] == "suv"
    assert updated.json()["is_ev"] is True
    assert updated.json()["registration_no"] is None

    deleted = client.delete(f"/api/v1/vehicles/{vehicle['id']}", headers=headers)
    assert deleted.status_code == 204

    missing = client.get("/api/v1/vehicles", headers=headers)
    assert missing.status_code == 200
    assert missing.json() == []


def test_cross_user_vehicle_access_returns_404(
    client: TestClient,
    auth_user_factory: Callable[..., Any],
    token_for: Callable[..., str],
) -> None:
    owner = auth_user_factory(full_name="Vehicle Owner")
    other = auth_user_factory(full_name="Other User")
    owner_headers = auth_headers(token_for, owner)
    other_headers = auth_headers(token_for, other)

    created = client.post(
        "/api/v1/vehicles",
        headers=owner_headers,
        json={"vehicle_type": "hatchback"},
    )
    assert created.status_code == 201, created.text
    vehicle_id = created.json()["id"]

    patch = client.patch(
        f"/api/v1/vehicles/{vehicle_id}",
        headers=other_headers,
        json={"vehicle_type": "suv"},
    )
    delete = client.delete(f"/api/v1/vehicles/{vehicle_id}", headers=other_headers)

    assert patch.status_code == 404
    assert patch.json()["error"]["code"] == "NOT_FOUND"
    assert delete.status_code == 404


def test_vehicle_limit_is_enforced(
    client: TestClient,
    auth_user_factory: Callable[..., Any],
    token_for: Callable[..., str],
) -> None:
    user = auth_user_factory(full_name="Ten Cars")
    headers = auth_headers(token_for, user)

    for index in range(10):
        response = client.post(
            "/api/v1/vehicles",
            headers=headers,
            json={"vehicle_type": "sedan", "registration_no": f"MH12AA{index:04d}"},
        )
        assert response.status_code == 201, response.text

    rejected = client.post(
        "/api/v1/vehicles",
        headers=headers,
        json={"vehicle_type": "sedan"},
    )

    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "VALIDATION_ERROR"


def test_vehicle_validation_rejects_unknown_type(
    client: TestClient,
    auth_user_factory: Callable[..., Any],
    token_for: Callable[..., str],
) -> None:
    user = auth_user_factory()

    response = client.post(
        "/api/v1/vehicles",
        headers=auth_headers(token_for, user),
        json={"vehicle_type": "spaceship"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_vehicle_routes_require_auth(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/vehicles")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_vehicle_routes_reject_missing_local_profile(
    client: TestClient,
    auth_user_factory: Callable[..., Any],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    user = auth_user_factory()
    db_execute("DELETE FROM sthalo.users WHERE id = $1", user.id)

    response = client.get(
        "/api/v1/vehicles",
        headers=auth_headers(token_for, user),
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
