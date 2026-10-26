"""FastAPI dependency for the private photo store."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from app.integrations.storage.supabase import PhotoStorage


def get_photo_storage(request: Request) -> PhotoStorage:
    storage = getattr(request.app.state, "photo_storage", None)
    if storage is None:
        raise RuntimeError("Photo storage is not configured")
    return cast(PhotoStorage, storage)
