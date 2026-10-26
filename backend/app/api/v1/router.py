"""Version 1 API router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.identity.router import router as identity_router
from app.modules.profiles.router import router as profiles_router

router = APIRouter(prefix="/api/v1")
router.include_router(identity_router)
router.include_router(profiles_router)
