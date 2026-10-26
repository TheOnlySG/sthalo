"""Create the private listing-photos bucket in local Supabase Storage."""

from __future__ import annotations

import asyncio

import httpx

from app.core.config import get_settings


async def main() -> None:
    settings = get_settings()
    key = settings.supabase_service_role_key.get_secret_value()
    url = f"{settings.supabase_url}/storage/v1/bucket"
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    payload = {
        "id": "listing-photos",
        "name": "listing-photos",
        "public": False,
        "file_size_limit": settings.max_upload_bytes,
        "allowed_mime_types": ["image/jpeg", "image/png", "image/webp"],
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code in {200, 201}:
            print("Created private bucket listing-photos.")
            return
        existing = await client.get(
            f"{settings.supabase_url}/storage/v1/bucket/listing-photos",
            headers=headers,
        )
        if existing.status_code == 200:
            print("Private bucket listing-photos already exists.")
            return
        response.raise_for_status()
        print(response.text)


if __name__ == "__main__":
    asyncio.run(main())
