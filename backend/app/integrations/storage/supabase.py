"""Private Supabase Storage adapter for listing photos."""

from __future__ import annotations

from typing import Protocol

import httpx
import structlog

from app.core.config import Settings

_logger = structlog.get_logger("sthalo.storage")
BUCKET = "listing-photos"


class PhotoStorageError(RuntimeError):
    """Raised when the private photo store cannot satisfy a request."""


class PhotoStorage(Protocol):
    async def upload(self, key: str, data: bytes, content_type: str) -> None: ...

    async def delete(self, key: str) -> None: ...

    async def signed_url(self, key: str, expires_in: int = 3600) -> str: ...


class SupabasePhotoStorage:
    """Small async client for the private listing-photos bucket."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.supabase_url.rstrip("/")
        self._service_key = settings.supabase_service_role_key.get_secret_value()
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0))

    async def close(self) -> None:
        await self._client.aclose()

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        url = f"{self._base_url}/storage/v1/object/{BUCKET}/{key}"
        try:
            response = await self._client.post(
                url,
                content=data,
                headers={
                    **self._auth_headers(),
                    "Content-Type": content_type,
                    "x-upsert": "false",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            _logger.error("photo_upload_failed", key=key, error=type(exc).__name__)
            raise PhotoStorageError("Photo storage upload failed.") from exc

    async def delete(self, key: str) -> None:
        url = f"{self._base_url}/storage/v1/object/{BUCKET}/{key}"
        try:
            response = await self._client.delete(url, headers=self._auth_headers())
            if response.status_code not in {200, 204, 404}:
                response.raise_for_status()
        except httpx.HTTPError as exc:
            _logger.error("photo_delete_failed", key=key, error=type(exc).__name__)
            raise PhotoStorageError("Photo storage delete failed.") from exc

    async def signed_url(self, key: str, expires_in: int = 3600) -> str:
        url = f"{self._base_url}/storage/v1/object/sign/{BUCKET}/{key}"
        try:
            response = await self._client.post(
                url,
                json={"expiresIn": expires_in},
                headers=self._auth_headers(),
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            _logger.error("photo_sign_failed", key=key, error=type(exc).__name__)
            raise PhotoStorageError("Photo storage signing failed.") from exc

        signed = payload.get("signedURL") if isinstance(payload, dict) else None
        if not isinstance(signed, str) or not signed:
            raise PhotoStorageError("Photo storage returned an invalid signed URL.")
        if signed.startswith(("http://", "https://")):
            return signed
        return f"{self._base_url}/storage/v1{signed}"

    def _auth_headers(self) -> dict[str, str]:
        return {
            "apikey": self._service_key,
            "Authorization": f"Bearer {self._service_key}",
        }
