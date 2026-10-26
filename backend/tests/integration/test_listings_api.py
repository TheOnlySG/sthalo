"""Database-backed V2 listing, photo, and moderation API tests."""

from __future__ import annotations

import math
from collections.abc import Callable
from io import BytesIO
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from PIL import Image
from tests.integration.conftest import FakePhotoStorage, TestUser

BASE = "/api/v1"
EXACT_LAT = 12.9716
EXACT_LNG = 77.5946


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _accept_terms(client: TestClient, token: str) -> None:
    response = client.post(f"{BASE}/users/me/accept-owner-terms", headers=_headers(token))
    assert response.status_code == 200, response.text


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "Covered driveway in Indiranagar",
        "description": "A clean covered driveway with easy access from the main road.",
        "latitude": EXACT_LAT,
        "longitude": EXACT_LNG,
        "address_line": "123 12th Main Road",
        "locality": "Indiranagar",
        "city": "Bengaluru",
        "state": "Karnataka",
        "pincode": "560038",
        "owner_terms_accepted": True,
        "parking": {
            "parking_type": "driveway",
            "supported_vehicle_types": ["hatchback", "sedan"],
            "max_length_mm": 4700,
            "max_width_mm": 1900,
            "max_height_mm": 1800,
            "is_covered": True,
            "access_method": "code",
            "access_instructions": "Use gate code 4455 and park in bay two.",
            "amenities": ["cctv", "lighting"],
            "restrictions": "No overnight commercial vehicles.",
            "pricing_model": "hourly_with_daily_cap",
            "price_hourly_paise": 5000,
            "price_daily_cap_paise": 30000,
            "min_booking_minutes": 60,
            "max_booking_minutes": 1440,
            "advance_booking_max_days": 30,
        },
    }
    payload.update(overrides)
    return payload


def _image(color: tuple[int, int, int] = (30, 120, 200)) -> bytes:
    output = BytesIO()
    Image.new("RGB", (320, 240), color).save(output, format="JPEG")
    return output.getvalue()


def _create_listing(client: TestClient, token: str, **overrides: Any) -> dict[str, Any]:
    response = client.post(
        f"{BASE}/owner/parking-listings",
        headers=_headers(token),
        json=_payload(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _upload_photo(
    client: TestClient,
    token: str,
    listing_id: str,
    content: bytes | None = None,
) -> dict[str, Any]:
    response = client.post(
        f"{BASE}/owner/parking-listings/{listing_id}/photos",
        headers=_headers(token),
        files={"file": ("photo.jpg", content or _image(), "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _approve(
    client: TestClient,
    admin_token: str,
    listing_id: str,
) -> dict[str, Any]:
    response = client.post(
        f"{BASE}/admin/listings/{listing_id}/approve",
        headers=_headers(admin_token),
        json={"note": "Looks good."},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _make_admin(
    db_execute: Callable[..., str],
    auth_user_factory: Callable[..., TestUser],
) -> TestUser:
    admin = auth_user_factory(email="admin@example.invalid", full_name="Admin Person")
    db_execute("UPDATE sthalo.users SET is_admin = true WHERE id = $1", admin.id)
    return admin


def _distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def test_create_listing_requires_owner_terms(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)

    response = client.post(
        f"{BASE}/owner/parking-listings",
        headers=_headers(token),
        json=_payload(),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_owner_can_create_draft_with_default_resource(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_fetchval: Callable[..., object],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)

    listing = _create_listing(client, token)

    assert listing["status"] == "draft"
    assert listing["photos"] == []
    assert listing["parking"]["access_instructions"].startswith("Use gate code")
    resource_label = db_fetchval(
        "SELECT label FROM sthalo.resources WHERE listing_id = $1",
        UUID(listing["id"]),
    )
    assert resource_label == "Main bay"
    public = client.get(f"{BASE}/parking-listings/{listing['id']}")
    assert public.status_code == 404


def test_non_owner_cannot_read_or_edit_listing(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
) -> None:
    owner = auth_user_factory()
    owner_token = token_for(owner)
    _accept_terms(client, owner_token)
    listing = _create_listing(client, owner_token)
    other = auth_user_factory()
    other_token = token_for(other)
    _accept_terms(client, other_token)

    read = client.get(
        f"{BASE}/owner/parking-listings/{listing['id']}",
        headers=_headers(other_token),
    )
    update = client.patch(
        f"{BASE}/owner/parking-listings/{listing['id']}",
        headers=_headers(other_token),
        json={"title": "A different listing title"},
    )

    assert read.status_code == 404
    assert update.status_code == 404


def test_submit_requires_declaration_and_photo(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    listing = _create_listing(client, token)

    no_declaration = client.post(
        f"{BASE}/owner/parking-listings/{listing['id']}/submit",
        headers=_headers(token),
        json={"declaration_accepted": False},
    )
    no_photo = client.post(
        f"{BASE}/owner/parking-listings/{listing['id']}/submit",
        headers=_headers(token),
        json={"declaration_accepted": True},
    )

    assert no_declaration.status_code == 422
    assert no_declaration.json()["error"]["code"] == "INCOMPLETE_LISTING"
    assert no_photo.status_code == 422
    assert no_photo.json()["error"]["code"] == "INCOMPLETE_LISTING"


def test_photo_validation_rejects_non_image(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    listing = _create_listing(client, token)

    response = client.post(
        f"{BASE}/owner/parking-listings/{listing['id']}/photos",
        headers=_headers(token),
        files={"file": ("note.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UPLOAD_INVALID"


def test_photo_cover_reorder_and_delete(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    listing = _create_listing(client, token)
    listing = _upload_photo(client, token, listing["id"], _image((200, 10, 10)))
    listing = _upload_photo(client, token, listing["id"], _image((10, 200, 10)))
    listing = _upload_photo(client, token, listing["id"], _image((10, 10, 200)))
    photos = listing["photos"]
    assert [photo["position"] for photo in photos] == [0, 1, 2]
    assert photos[0]["is_cover"] is True

    reorder = client.patch(
        f"{BASE}/owner/parking-listings/{listing['id']}/photos/{photos[2]['id']}",
        headers=_headers(token),
        json={"position": 0, "is_cover": True},
    )

    assert reorder.status_code == 200, reorder.text
    reordered = {item["id"]: item for item in reorder.json()["photos"]}
    assert reordered[photos[2]["id"]]["position"] == 0
    assert reordered[photos[2]["id"]]["is_cover"] is True
    assert reordered[photos[0]["id"]]["position"] == 2
    assert reordered[photos[0]["id"]]["is_cover"] is False

    deleted = client.delete(
        f"{BASE}/owner/parking-listings/{listing['id']}/photos/{photos[2]['id']}",
        headers=_headers(token),
    )
    assert deleted.status_code == 204, deleted.text
    remaining = client.get(
        f"{BASE}/owner/parking-listings/{listing['id']}",
        headers=_headers(token),
    ).json()["photos"]
    assert [photo["position"] for photo in remaining] == [0, 1]
    assert sum(1 for photo in remaining if photo["is_cover"]) == 1


def test_submit_approve_public_and_hide_private_fields(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
    photo_storage: FakePhotoStorage,
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    listing = _create_listing(client, token)
    _upload_photo(client, token, listing["id"])
    submitted = client.post(
        f"{BASE}/owner/parking-listings/{listing['id']}/submit",
        headers=_headers(token),
        json={"declaration_accepted": True},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "pending_review"
    assert client.get(f"{BASE}/parking-listings/{listing['id']}").status_code == 404

    admin = _make_admin(db_execute, auth_user_factory)
    admin_token = token_for(admin)
    queue = client.get(
        f"{BASE}/admin/listings",
        headers=_headers(admin_token),
        params={"status": "pending_review"},
    )
    assert queue.status_code == 200, queue.text
    assert listing["id"] in {item["id"] for item in queue.json()}

    approved = _approve(client, admin_token, listing["id"])
    assert approved["status"] == "active"
    assert approved["owner"]["email"] == owner.email

    public = client.get(f"{BASE}/parking-listings/{listing['id']}")
    assert public.status_code == 200, public.text
    body = public.json()
    assert "address_line" not in body
    assert "pincode" not in body
    assert "access_instructions" not in body["parking"]
    assert body["latitude"] != EXACT_LAT
    assert 70 <= _distance_m(EXACT_LAT, EXACT_LNG, body["latitude"], body["longitude"]) <= 220
    assert len(body["photos"]) == 1
    assert body["photos"][0]["url"].startswith("http://storage.test/")
    assert len(photo_storage.objects) == 1


def test_editing_active_listing_returns_to_pending(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    listing = _create_listing(client, token)
    _upload_photo(client, token, listing["id"])
    client.post(
        f"{BASE}/owner/parking-listings/{listing['id']}/submit",
        headers=_headers(token),
        json={"declaration_accepted": True},
    )
    admin = _make_admin(db_execute, auth_user_factory)
    _approve(client, token_for(admin), listing["id"])

    edited = client.patch(
        f"{BASE}/owner/parking-listings/{listing['id']}",
        headers=_headers(token),
        json={"title": "Updated covered driveway listing"},
    )

    assert edited.status_code == 200, edited.text
    assert edited.json()["status"] == "pending_review"
    assert client.get(f"{BASE}/parking-listings/{listing['id']}").status_code == 404


def test_reject_suspend_and_restore_flow(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    listing = _create_listing(client, token)
    _upload_photo(client, token, listing["id"])
    client.post(
        f"{BASE}/owner/parking-listings/{listing['id']}/submit",
        headers=_headers(token),
        json={"declaration_accepted": True},
    )
    admin = _make_admin(db_execute, auth_user_factory)
    admin_token = token_for(admin)

    rejected = client.post(
        f"{BASE}/admin/listings/{listing['id']}/reject",
        headers=_headers(admin_token),
        json={"note": "Please add clearer access photos."},
    )
    assert rejected.status_code == 200, rejected.text
    rejected_owner = client.get(
        f"{BASE}/owner/parking-listings/{listing['id']}",
        headers=_headers(token),
    ).json()
    assert rejected_owner["status"] == "rejected"
    assert rejected_owner["moderation_note"] == "Please add clearer access photos."

    edited = client.patch(
        f"{BASE}/owner/parking-listings/{listing['id']}",
        headers=_headers(token),
        json={"title": "Clearer covered driveway listing"},
    )
    assert edited.json()["status"] == "draft"

    resubmitted = client.post(
        f"{BASE}/owner/parking-listings/{listing['id']}/submit",
        headers=_headers(token),
        json={"declaration_accepted": True},
    )
    assert resubmitted.json()["status"] == "pending_review"
    _approve(client, admin_token, listing["id"])

    suspended = client.post(
        f"{BASE}/admin/listings/{listing['id']}/suspend",
        headers=_headers(admin_token),
        json={"note": "Safety complaint under review."},
    )
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["status"] == "suspended"
    assert client.get(f"{BASE}/parking-listings/{listing['id']}").status_code == 404

    restored = client.post(
        f"{BASE}/admin/listings/{listing['id']}/restore",
        headers=_headers(admin_token),
        json={"note": "Complaint resolved."},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["status"] == "active"
    owner_after = client.get(
        f"{BASE}/owner/parking-listings/{listing['id']}",
        headers=_headers(token),
    ).json()
    assert owner_after["moderation_note"] is None


def test_pause_resume_archive_and_admin_auth(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    listing = _create_listing(client, token)
    _upload_photo(client, token, listing["id"])
    client.post(
        f"{BASE}/owner/parking-listings/{listing['id']}/submit",
        headers=_headers(token),
        json={"declaration_accepted": True},
    )
    admin = _make_admin(db_execute, auth_user_factory)
    admin_token = token_for(admin)
    _approve(client, admin_token, listing["id"])

    forbidden = client.get(f"{BASE}/admin/listings", headers=_headers(token))
    assert forbidden.status_code == 403

    paused = client.post(
        f"{BASE}/owner/parking-listings/{listing['id']}/pause",
        headers=_headers(token),
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["status"] == "paused"
    assert client.get(f"{BASE}/parking-listings/{listing['id']}").status_code == 404

    resumed = client.post(
        f"{BASE}/owner/parking-listings/{listing['id']}/resume",
        headers=_headers(token),
    )
    assert resumed.status_code == 200, resumed.text
    assert client.get(f"{BASE}/parking-listings/{listing['id']}").status_code == 200

    archived = client.post(
        f"{BASE}/owner/parking-listings/{listing['id']}/archive",
        headers=_headers(token),
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "archived"
    assert client.get(f"{BASE}/parking-listings/{listing['id']}").status_code == 404


def test_archive_is_blocked_by_future_reservation(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
    db_fetchrow: Callable[..., object],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    listing = _create_listing(client, token)
    resource = db_fetchrow(
        "SELECT id FROM sthalo.resources WHERE listing_id = $1",
        UUID(listing["id"]),
    )
    vehicle = client.post(
        f"{BASE}/vehicles",
        headers=_headers(token),
        json={"vehicle_type": "sedan"},
    ).json()
    assert resource is not None
    db_execute(
        """
        INSERT INTO sthalo.reservations (
            reference, customer_id, owner_id, listing_id, resource_id,
            vehicle_id, time_range, status, currency, base_amount_paise,
            total_paise, price_snapshot
        ) VALUES (
            $1, $2, $2, $3, $4, $5,
            tstzrange(now() + interval '1 day', now() + interval '2 days'),
            'confirmed', 'INR', 1000, 1000, '{}'::jsonb
        )
        """,
        f"TEST-{listing['id'][:8]}",
        owner.id,
        UUID(listing["id"]),
        resource["id"],
        UUID(vehicle["id"]),
    )

    response = client.post(
        f"{BASE}/owner/parking-listings/{listing['id']}/archive",
        headers=_headers(token),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "HAS_FUTURE_BOOKINGS"


def test_pending_listing_photos_can_change_but_fields_cannot(
    client: TestClient,
    auth_user_factory: Callable[..., TestUser],
    token_for: Callable[..., str],
) -> None:
    owner = auth_user_factory()
    token = token_for(owner)
    _accept_terms(client, token)
    listing = _create_listing(client, token)
    _upload_photo(client, token, listing["id"])
    client.post(
        f"{BASE}/owner/parking-listings/{listing['id']}/submit",
        headers=_headers(token),
        json={"declaration_accepted": True},
    )

    field_update = client.patch(
        f"{BASE}/owner/parking-listings/{listing['id']}",
        headers=_headers(token),
        json={"title": "A new title while pending review"},
    )
    photo_update = client.post(
        f"{BASE}/owner/parking-listings/{listing['id']}/photos",
        headers=_headers(token),
        files={"file": ("second.jpg", _image((90, 20, 160)), "image/jpeg")},
    )

    assert field_update.status_code == 409
    assert field_update.json()["error"]["code"] == "INVALID_STATE_TRANSITION"
    assert photo_update.status_code == 201, photo_update.text
    assert photo_update.json()["status"] == "pending_review"
    assert len(photo_update.json()["photos"]) == 2

    first_photo_id = photo_update.json()["photos"][0]["id"]
    photo_edit = client.patch(
        f"{BASE}/owner/parking-listings/{listing['id']}/photos/{first_photo_id}",
        headers=_headers(token),
        json={"position": 1, "is_cover": True},
    )
    assert photo_edit.status_code == 200, photo_edit.text
    assert photo_edit.json()["status"] == "pending_review"
    edited_photos = {photo["id"]: photo for photo in photo_edit.json()["photos"]}
    assert edited_photos[first_photo_id]["position"] == 1
    assert edited_photos[first_photo_id]["is_cover"] is True
