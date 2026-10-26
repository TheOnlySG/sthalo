"""Framework-level dependencies shared by API routers."""

from __future__ import annotations

from fastapi import Request

from app.core.config import Settings


def get_application_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        raise RuntimeError("Application settings are not configured")
    return settings
