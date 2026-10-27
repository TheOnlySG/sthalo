"""Seed labeled demo accounts, listings, vehicles, and a reservation.

Usage:
    backend/.venv/bin/python backend/scripts/seed_demo.py
    backend/.venv/bin/python backend/scripts/seed_demo.py --cleanup
    backend/.venv/bin/python backend/scripts/seed_demo.py --api-base-url https://api.example.com/api/v1
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_ROOT / ".env"
MAKE_ADMIN = BACKEND_ROOT / "scripts" / "make_admin.py"
DEMO_TZ = ZoneInfo("Asia/Kolkata")
DEMO_PASSWORD_ENV = "STHALO_DEMO_PASSWORD"
DEMO_MARKER = "[DEMO]"
BUCKET = "listing-photos"

DEMO_USERS = {
    "owner": ("owner@demo.sthalo.invalid", "Demo Owner"),
    "customer": ("customer@demo.sthalo.invalid", "Demo Customer"),
    "admin": ("admin@demo.sthalo.invalid", "Demo Admin"),
}

DEMO_LISTINGS: tuple[dict[str, Any], ...] = (
    {
        "title": f"{DEMO_MARKER} College Road covered driveway",
        "description": (
            "Synthetic demonstration driveway near College Road. Not a real parking "
            "space; created only for Sthalo demos and QA."
        ),
        "latitude": 19.9975,
        "longitude": 73.7898,
        "address_line": "Demo address, College Road",
        "locality": "College Road",
        "city": "Nashik",
        "state": "Maharashtra",
        "pincode": "422005",
        "parking": {
            "parking_type": "driveway",
            "supported_vehicle_types": ["hatchback", "sedan"],
            "max_length_mm": 4700,
            "max_width_mm": 1900,
            "max_height_mm": 1800,
            "is_covered": True,
            "access_method": "code",
            "access_instructions": "Demo gate code 2468. Park in the marked bay only.",
            "amenities": ["cctv", "lighting"],
            "restrictions": "Demo listing only. No commercial vehicles.",
            "pricing_model": "hourly_with_daily_cap",
            "price_hourly_paise": 5000,
            "price_daily_cap_paise": 30000,
            "min_booking_minutes": 60,
            "max_booking_minutes": 1440,
            "advance_booking_max_days": 30,
        },
    },
    {
        "title": f"{DEMO_MARKER} Panchavati secure garage",
        "description": (
            "Synthetic demonstration garage in Panchavati for product walkthroughs. "
            "The address and access details are fictitious."
        ),
        "latitude": 20.0110,
        "longitude": 73.7920,
        "address_line": "Demo address, Panchavati",
        "locality": "Panchavati",
        "city": "Nashik",
        "state": "Maharashtra",
        "pincode": "422003",
        "parking": {
            "parking_type": "garage",
            "supported_vehicle_types": ["hatchback", "sedan", "suv"],
            "max_length_mm": 5200,
            "max_width_mm": 2100,
            "max_height_mm": 2100,
            "is_covered": True,
            "access_method": "key_handover",
            "access_instructions": "Demo host will hand over the garage key at the gate.",
            "amenities": ["cctv", "lighting", "ev_charging"],
            "restrictions": "Synthetic demo space. No overnight commercial parking.",
            "pricing_model": "hourly",
            "price_hourly_paise": 7000,
            "price_daily_cap_paise": None,
            "min_booking_minutes": 60,
            "max_booking_minutes": 720,
            "advance_booking_max_days": 30,
        },
    },
    {
        "title": f"{DEMO_MARKER} Gangapur Road open bay",
        "description": (
            "Synthetic demonstration open-air bay near Gangapur Road. Use for UI "
            "demo purposes only; it does not represent a real property."
        ),
        "latitude": 20.0015,
        "longitude": 73.7740,
        "address_line": "Demo address, Gangapur Road",
        "locality": "Gangapur Road",
        "city": "Nashik",
        "state": "Maharashtra",
        "pincode": "422013",
        "parking": {
            "parking_type": "open_lot",
            "supported_vehicle_types": ["hatchback", "sedan", "suv", "large"],
            "max_length_mm": None,
            "max_width_mm": None,
            "max_height_mm": None,
            "is_covered": False,
            "access_method": "open",
            "access_instructions": "Demo bay is open during the posted availability.",
            "amenities": ["lighting"],
            "restrictions": "Demo listing only. Do not leave valuables in the vehicle.",
            "pricing_model": "flat_daily",
            "price_hourly_paise": None,
            "price_daily_cap_paise": 25000,
            "min_booking_minutes": 60,
            "max_booking_minutes": 1440,
            "advance_booking_max_days": 30,
        },
    },
)

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAGUlEQVR4nGOUqzjBQApgIkn1qIZRDUNKAwBgxgF+DAqMFgAAAABJRU5ErkJggg=="
)


class SeedError(RuntimeError):
    """Raised when a demo seed operation cannot be completed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("STHALO_API_BASE_URL", "http://127.0.0.1:8000/api/v1"),
        help="Sthalo API base URL",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get(DEMO_PASSWORD_ENV),
        help=f"Demo-only password for all seeded accounts; defaults to ${DEMO_PASSWORD_ENV}",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete demo users, their cascaded rows, and their uploaded demo photos",
    )
    parser.add_argument(
        "--confirm-demo-project",
        action="store_true",
        help="Required for non-local environments; confirms this is the dedicated demo project",
    )
    return parser.parse_args()


def _service_headers(settings: Settings) -> dict[str, str]:
    key = settings.supabase_service_role_key.get_secret_value()
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _dsn(settings: Settings) -> str:
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


async def _api(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    token: str | None = None,
    expected: tuple[int, ...] = (200, 201),
    **kwargs: Any,
) -> httpx.Response:
    headers = dict(kwargs.pop("headers", {}))
    if token is not None:
        headers.update(_auth_headers(token))
    response = await client.request(method, url, headers=headers, **kwargs)
    if response.status_code not in expected:
        raise SeedError(f"{method} {url} failed: {response.status_code} {response.text}")
    return response


async def _list_auth_users(client: httpx.AsyncClient, settings: Settings) -> list[dict[str, Any]]:
    users: list[dict[str, Any]] = []
    page = 1
    while True:
        response = await client.get(
            f"{settings.supabase_url}/auth/v1/admin/users",
            headers=_service_headers(settings),
            params={"page": page, "per_page": 100},
        )
        if response.status_code != 200:
            raise SeedError(f"list auth users failed: {response.status_code} {response.text}")
        payload = response.json()
        batch = payload if isinstance(payload, list) else payload.get("users", [])
        users.extend(batch)
        if len(batch) < 100:
            return users
        page += 1


async def _ensure_auth_user(
    client: httpx.AsyncClient,
    settings: Settings,
    email: str,
    full_name: str,
    password: str,
) -> dict[str, Any]:
    service_headers = _service_headers(settings)
    existing = next(
        (user for user in await _list_auth_users(client, settings) if user.get("email") == email),
        None,
    )
    body = {
        "password": password,
        "email_confirm": True,
        "user_metadata": {"full_name": full_name},
    }
    if existing is not None:
        response = await client.put(
            f"{settings.supabase_url}/auth/v1/admin/users/{existing['id']}",
            headers=service_headers,
            json=body,
        )
        if response.status_code != 200:
            raise SeedError(f"update auth user {email} failed: {response.status_code}")
        return response.json()

    response = await client.post(
        f"{settings.supabase_url}/auth/v1/admin/users",
        headers=service_headers,
        json={"email": email, **body},
    )
    if response.status_code in (200, 201):
        return response.json()
    if response.status_code == 422:
        for user in await _list_auth_users(client, settings):
            if user.get("email") == email:
                return user
    raise SeedError(f"create auth user {email} failed: {response.status_code} {response.text}")


async def _sign_in(client: httpx.AsyncClient, settings: Settings, email: str, password: str) -> str:
    response = await client.post(
        f"{settings.supabase_url}/auth/v1/token",
        headers={
            "apikey": settings.supabase_anon_key.get_secret_value(),
            "Content-Type": "application/json",
        },
        params={"grant_type": "password"},
        json={"email": email, "password": password},
    )
    if response.status_code != 200:
        raise SeedError(f"sign in {email} failed: {response.status_code} {response.text}")
    return str(response.json()["access_token"])


def _promote_admin(email: str) -> None:
    result = subprocess.run(
        [sys.executable, str(MAKE_ADMIN), "--email", email],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SeedError(f"admin promotion failed: {result.stderr.strip() or result.stdout.strip()}")


async def _existing_listings(
    client: httpx.AsyncClient, api_base: str, owner_token: str
) -> dict[str, dict[str, Any]]:
    response = await _api(
        client,
        "GET",
        f"{api_base}/owner/parking-listings",
        token=owner_token,
    )
    return {item["title"]: item for item in response.json()}


async def _upload_photo(
    client: httpx.AsyncClient, api_base: str, owner_token: str, listing_id: str
) -> None:
    await _api(
        client,
        "POST",
        f"{api_base}/owner/parking-listings/{listing_id}/photos",
        token=owner_token,
        files={"file": ("demo.png", TINY_PNG, "image/png")},
    )


async def _promote_listing(
    client: httpx.AsyncClient,
    api_base: str,
    owner_token: str,
    admin_token: str,
    listing: dict[str, Any],
) -> str:
    if listing["status"] == "active":
        return str(listing["id"])
    if listing["status"] in ("draft", "rejected"):
        if not listing.get("photo_count"):
            await _upload_photo(client, api_base, owner_token, str(listing["id"]))
        await _api(
            client,
            "POST",
            f"{api_base}/owner/parking-listings/{listing['id']}/submit",
            token=owner_token,
            json={"declaration_accepted": True},
        )
    elif listing["status"] == "paused":
        await _api(
            client,
            "POST",
            f"{api_base}/owner/parking-listings/{listing['id']}/resume",
            token=owner_token,
            expected=(200,),
        )
        return str(listing["id"])
    elif listing["status"] not in ("pending_review", "rejected"):
        raise SeedError(f"listing {listing['id']} has unsupported status {listing['status']}")

    await _api(
        client,
        "POST",
        f"{api_base}/admin/listings/{listing['id']}/approve",
        token=admin_token,
        json={"note": "Seeded labeled demo data"},
    )
    return str(listing["id"])


async def _ensure_listing(
    client: httpx.AsyncClient,
    api_base: str,
    owner_token: str,
    admin_token: str,
    existing: dict[str, dict[str, Any]],
    data: dict[str, Any],
) -> str:
    current = existing.get(data["title"])
    if current is None:
        response = await _api(
            client,
            "POST",
            f"{api_base}/owner/parking-listings",
            token=owner_token,
            json={**data, "owner_terms_accepted": True},
        )
        listing_id = str(response.json()["id"])
        await _upload_photo(client, api_base, owner_token, listing_id)
        await _api(
            client,
            "POST",
            f"{api_base}/owner/parking-listings/{listing_id}/submit",
            token=owner_token,
            json={"declaration_accepted": True},
        )
        await _api(
            client,
            "POST",
            f"{api_base}/admin/listings/{listing_id}/approve",
            token=admin_token,
            json={"note": "Seeded labeled demo data"},
        )
    else:
        listing_id = await _promote_listing(client, api_base, owner_token, admin_token, current)

    await _api(
        client,
        "PUT",
        f"{api_base}/owner/parking-listings/{listing_id}/availability-rules",
        token=owner_token,
        json={
            "rules": [
                {"weekday": weekday, "start_time": "09:00:00", "end_time": "18:00:00"}
                for weekday in range(1, 8)
            ]
        },
    )
    return listing_id


async def _ensure_vehicle(client: httpx.AsyncClient, api_base: str, customer_token: str) -> str:
    response = await _api(client, "GET", f"{api_base}/vehicles", token=customer_token)
    for vehicle in response.json():
        if vehicle["registration_no"] == "DEMO01":
            return str(vehicle["id"])
    created = await _api(
        client,
        "POST",
        f"{api_base}/vehicles",
        token=customer_token,
        json={
            "vehicle_type": "hatchback",
            "registration_no": "DEMO01",
            "length_mm": 4000,
            "width_mm": 1800,
            "height_mm": 1600,
        },
    )
    return str(created.json()["id"])


async def _ensure_reservation(
    client: httpx.AsyncClient,
    api_base: str,
    customer_token: str,
    listing_id: str,
    vehicle_id: str,
) -> None:
    response = await _api(client, "GET", f"{api_base}/reservations/me", token=customer_token)
    live = [
        item
        for item in response.json()
        if str(item["listing"]["id"]) == listing_id
        and item["status"] in ("pending_confirmation", "confirmed", "active")
    ]
    for item in live:
        if item["status"] == "pending_confirmation":
            await _api(
                client,
                "POST",
                f"{api_base}/reservations/{item['id']}/confirm",
                token=customer_token,
                headers={"Idempotency-Key": f"seed-confirm-{item['id']}"},
            )
        return

    start = datetime.now(DEMO_TZ).replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(
        days=1
    )
    end = start + timedelta(hours=2)
    payload = {
        "listing_id": listing_id,
        "vehicle_id": vehicle_id,
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
    created = await _api(
        client,
        "POST",
        f"{api_base}/reservations",
        token=customer_token,
        headers={"Idempotency-Key": f"seed-hold-{listing_id}-{start.date().isoformat()}"},
        json=payload,
    )
    reservation_id = str(created.json()["id"])
    await _api(
        client,
        "POST",
        f"{api_base}/reservations/{reservation_id}/confirm",
        token=customer_token,
        headers={"Idempotency-Key": f"seed-confirm-{reservation_id}"},
    )


async def _cleanup_storage(settings: Settings) -> None:
    emails = [email.lower() for email, _ in DEMO_USERS.values()]
    connection = await asyncpg.connect(_dsn(settings))
    try:
        rows = await connection.fetch(
            """
            SELECT lp.storage_key
            FROM sthalo.listing_photos AS lp
            JOIN sthalo.listings AS l ON l.id = lp.listing_id
            JOIN sthalo.users AS u ON u.id = l.owner_id
            WHERE lower(u.email) = ANY($1::text[])
            """,
            emails,
        )
    finally:
        await connection.close()
    keys = [str(row["storage_key"]) for row in rows]
    if not keys:
        return
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(
            "DELETE",
            f"{settings.supabase_url}/storage/v1/object/{BUCKET}",
            headers=_service_headers(settings),
            content=json.dumps({"prefixes": keys}),
        )
        if response.status_code not in (200, 204):
            raise SeedError(f"delete demo photos failed: {response.status_code} {response.text}")


async def cleanup(client: httpx.AsyncClient, settings: Settings) -> None:
    emails = {email for email, _ in DEMO_USERS.values()}
    await _cleanup_storage(settings)
    users = [
        user for user in await _list_auth_users(client, settings) if user.get("email") in emails
    ]
    for user in users:
        await _api(
            client,
            "DELETE",
            f"{settings.supabase_url}/auth/v1/admin/users/{user['id']}",
            token=None,
            expected=(200, 204),
            headers=_service_headers(settings),
        )
        print(f"Deleted demo auth user {user['email']}")
    if not users:
        print("No demo auth users found; nothing to delete.")


async def seed(args: argparse.Namespace) -> None:
    settings = Settings(_env_file=ENV_FILE)
    if settings.env.value not in ("local", "test") and not args.confirm_demo_project:
        raise SeedError(
            "non-local environment detected; pass --confirm-demo-project only for the "
            "dedicated demo project"
        )
    if not args.cleanup and not args.password:
        raise SeedError(f"set {DEMO_PASSWORD_ENV} or pass --password for the demo accounts")
    if not args.cleanup and (
        len(args.password) < 8
        or not any(character.isalpha() for character in args.password)
        or not any(character.isdigit() for character in args.password)
    ):
        raise SeedError("demo password must be at least 8 characters with letters and digits")
    api_base = args.api_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=60) as client:
        if args.cleanup:
            await cleanup(client, settings)
            return

        await _ensure_auth_user(
            client,
            settings,
            *DEMO_USERS["owner"],
            args.password,
        )
        await _ensure_auth_user(
            client,
            settings,
            *DEMO_USERS["customer"],
            args.password,
        )
        admin = await _ensure_auth_user(
            client,
            settings,
            *DEMO_USERS["admin"],
            args.password,
        )
        _promote_admin(str(admin["email"]))

        owner_token = await _sign_in(client, settings, DEMO_USERS["owner"][0], args.password)
        customer_token = await _sign_in(client, settings, DEMO_USERS["customer"][0], args.password)
        admin_token = await _sign_in(client, settings, DEMO_USERS["admin"][0], args.password)

        await _api(
            client,
            "POST",
            f"{api_base}/users/me/accept-owner-terms",
            token=owner_token,
        )

        existing = await _existing_listings(client, api_base, owner_token)
        listing_ids = [
            await _ensure_listing(
                client,
                api_base,
                owner_token,
                admin_token,
                existing,
                data,
            )
            for data in DEMO_LISTINGS
        ]
        vehicle_id = await _ensure_vehicle(client, api_base, customer_token)
        await _ensure_reservation(client, api_base, customer_token, listing_ids[0], vehicle_id)

    print("Seeded labeled demo data:")
    for label, (email, _) in DEMO_USERS.items():
        print(f"  {label:8} {email}")
    print(f"  listings {len(listing_ids)}")
    print(f"  password supplied through --password or {DEMO_PASSWORD_ENV}")


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(seed(args))
    except (SeedError, httpx.HTTPError, asyncpg.PostgresError) as exc:
        print(f"Demo seed failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
