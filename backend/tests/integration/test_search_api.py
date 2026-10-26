"""Database-backed V3 discovery search tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from tests.integration.conftest import TestUser
from tests.integration.test_listings_api import (
    BASE,
    _accept_terms,
    _approve,
    _create_listing,
    _distance_m,
    _headers,
    _make_admin,
    _payload,
    _upload_photo,
)

CENTER_LAT = 19.9975
CENTER_LNG = 73.7898
CENTER = {"lat": CENTER_LAT, "lng": CENTER_LNG}
NEARBY_BBOX = (73.70, 19.94, 73.87, 20.05)


def _parking(**overrides: Any) -> dict[str, Any]:
    parking = dict(_payload()["parking"])
    parking.update(overrides)
    return parking


def _submit(client: TestClient, token: str, listing_id: str) -> None:
    response = client.post(
        f"{BASE}/owner/parking-listings/{listing_id}/submit",
        headers=_headers(token),
        json={"declaration_accepted": True},
    )
    assert response.status_code == 200, response.text


def _activate(
    client: TestClient,
    token: str,
    admin_token: str,
    listing_id: str,
) -> None:
    _submit(client, token, listing_id)
    _approve(client, admin_token, listing_id)


def _nearby_listing(
    client: TestClient,
    token: str,
    admin_token: str,
    *,
    title: str,
    latitude: float,
    longitude: float,
    parking: dict[str, Any],
    approve: bool = True,
) -> dict[str, Any]:
    listing = _create_listing(
        client,
        token,
        title=title,
        latitude=latitude,
        longitude=longitude,
        parking=parking,
    )
    _upload_photo(client, token, listing["id"])
    _submit(client, token, listing["id"])
    if approve:
        _approve(client, admin_token, listing["id"])
    return listing


def _search(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get(f"{BASE}/search/parking", params=params)
    assert response.status_code == 200, response.text
    payload: dict[str, Any] = response.json()
    return payload


def test_radius_search_returns_only_active_privacy_safe_listings(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    admin = _make_admin(db_execute, auth_user_factory)
    admin_token = token_for(admin)

    active = _nearby_listing(
        client,
        token,
        admin_token,
        title="Active covered bay",
        latitude=CENTER_LAT,
        longitude=CENTER_LNG,
        parking=_parking(),
    )
    _create_listing(
        client,
        token,
        title="Draft nearby bay",
        latitude=CENTER_LAT,
        longitude=CENTER_LNG,
        parking=_parking(price_hourly_paise=1000, price_daily_cap_paise=2000),
    )
    _nearby_listing(
        client,
        token,
        admin_token,
        title="Pending nearby bay",
        latitude=CENTER_LAT,
        longitude=CENTER_LNG,
        parking=_parking(price_hourly_paise=2000, price_daily_cap_paise=3000),
        approve=False,
    )
    paused = _nearby_listing(
        client,
        token,
        admin_token,
        title="Paused nearby bay",
        latitude=CENTER_LAT,
        longitude=CENTER_LNG,
        parking=_parking(price_hourly_paise=3000, price_daily_cap_paise=4000),
    )
    paused_response = client.post(
        f"{BASE}/owner/parking-listings/{paused['id']}/pause",
        headers=_headers(token),
    )
    assert paused_response.status_code == 200, paused_response.text
    _nearby_listing(
        client,
        token,
        admin_token,
        title="Active far bay",
        latitude=19.95,
        longitude=73.80,
        parking=_parking(price_hourly_paise=4000, price_daily_cap_paise=5000),
    )

    body = _search(client, **CENTER, radius_m=3000, limit=20)

    assert body["mode"] == "radius"
    assert body["center_latitude"] == CENTER_LAT
    assert body["center_longitude"] == CENTER_LNG
    assert body["radius_m"] == 3000
    assert body["bbox"] is None
    assert body["sort"] == "distance"
    assert body["next_cursor"] is None
    assert [item["id"] for item in body["items"]] == [active["id"]]

    item = body["items"][0]
    assert item["title"] == "Active covered bay"
    assert "address_line" not in item
    assert "pincode" not in item
    assert "access_instructions" not in item["parking"]
    assert item["cover_url"].startswith("http://storage.test/")
    assert item["latitude"] != CENTER_LAT
    assert item["longitude"] != CENTER_LNG
    offset = _distance_m(CENTER_LAT, CENTER_LNG, item["latitude"], item["longitude"])
    assert 70 <= offset <= 220
    expected_distance = _distance_m(
        CENTER_LAT,
        CENTER_LNG,
        item["latitude"],
        item["longitude"],
    )
    assert abs(item["distance_m"] - expected_distance) < 1.0


def test_bbox_filters_and_price_sort(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    admin = _make_admin(db_execute, auth_user_factory)
    admin_token = token_for(admin)

    cheap = _nearby_listing(
        client,
        token,
        admin_token,
        title="Cheap hatchback bay",
        latitude=19.9975,
        longitude=73.7898,
        parking=_parking(
            supported_vehicle_types=["hatchback", "sedan"],
            is_covered=True,
            price_hourly_paise=5000,
            price_daily_cap_paise=30_000,
        ),
    )
    middle = _nearby_listing(
        client,
        token,
        admin_token,
        title="Uncovered SUV bay",
        latitude=20.0000,
        longitude=73.7900,
        parking=_parking(
            supported_vehicle_types=["suv"],
            is_covered=False,
            price_hourly_paise=8000,
            price_daily_cap_paise=40_000,
        ),
    )
    expensive = _nearby_listing(
        client,
        token,
        admin_token,
        title="Premium hatchback bay",
        latitude=20.0040,
        longitude=73.7940,
        parking=_parking(
            supported_vehicle_types=["hatchback"],
            is_covered=True,
            price_hourly_paise=12_000,
            price_daily_cap_paise=50_000,
        ),
    )
    bbox = ",".join(str(value) for value in NEARBY_BBOX)

    filtered = _search(
        client,
        bbox=bbox,
        vehicle_type="hatchback",
        covered=True,
        max_price_paise=6000,
    )
    assert filtered["mode"] == "bbox"
    assert filtered["bbox"] == list(NEARBY_BBOX)
    assert filtered["radius_m"] is None
    assert [item["id"] for item in filtered["items"]] == [cheap["id"]]

    ordered = _search(client, bbox=bbox, sort="price")
    assert [item["id"] for item in ordered["items"]] == [
        cheap["id"],
        middle["id"],
        expensive["id"],
    ]


def test_search_scope_and_cursor_validation(
    client: TestClient,
) -> None:
    missing_scope = client.get(f"{BASE}/search/parking")
    assert missing_scope.status_code == 422

    partial_scope = client.get(f"{BASE}/search/parking", params={"lat": CENTER_LAT})
    assert partial_scope.status_code == 422

    mixed_scope = client.get(
        f"{BASE}/search/parking",
        params={
            **CENTER,
            "radius_m": 1000,
            "bbox": "73.70,19.94,73.87,20.05",
        },
    )
    assert mixed_scope.status_code == 422

    oversized = client.get(
        f"{BASE}/search/parking",
        params={"bbox": "72.0,18.0,74.0,21.0"},
    )
    assert oversized.status_code == 422

    malformed = client.get(
        f"{BASE}/search/parking",
        params={"bbox": "not,a,valid,box"},
    )
    assert malformed.status_code == 422

    western_hemisphere = client.get(
        f"{BASE}/search/parking",
        params={"bbox": "-74.02,40.70,-73.94,40.78"},
    )
    assert western_hemisphere.status_code == 200
    assert western_hemisphere.json()["items"] == []

    cursor = client.get(
        f"{BASE}/search/parking",
        params={**CENTER, "cursor": "not-a-valid-cursor"},
    )
    assert cursor.status_code == 422
    assert cursor.json()["error"]["code"] == "VALIDATION_ERROR"


def test_cursor_pagination_is_stable(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    admin = _make_admin(db_execute, auth_user_factory)
    admin_token = token_for(admin)

    created = [
        _nearby_listing(
            client,
            token,
            admin_token,
            title=f"Paginated bay {index}",
            latitude=19.9975 + index * 0.0005,
            longitude=73.7898 + index * 0.0005,
            parking=_parking(
                price_hourly_paise=price,
                price_daily_cap_paise=price * 6,
            ),
        )
        for index, price in enumerate((3000, 5000, 7000))
    ]

    first = _search(client, **CENTER, radius_m=3000, sort="price", limit=2)
    assert len(first["items"]) == 2
    assert first["next_cursor"] is not None
    assert [item["id"] for item in first["items"]] == [
        created[0]["id"],
        created[1]["id"],
    ]

    second = _search(
        client,
        **CENTER,
        radius_m=3000,
        sort="price",
        limit=2,
        cursor=first["next_cursor"],
    )
    assert [item["id"] for item in second["items"]] == [created[2]["id"]]
    assert second["next_cursor"] is None
