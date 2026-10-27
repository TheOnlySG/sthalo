"""FastAPI application factory."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.health import router as health_router
from app.api.v1.router import router as api_v1_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from app.core.request_id import REQUEST_ID_HEADER, RequestIDMiddleware
from app.db.engine import build_engine, build_session_factory
from app.integrations.storage.supabase import SupabasePhotoStorage
from app.modules.reservations.sweeper import start_sweeper


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Create database resources on startup and dispose them on shutdown."""
    settings = application.state.settings
    if not isinstance(settings, Settings):
        raise RuntimeError("Application settings are not configured")
    engine = build_engine(settings)
    application.state.engine = engine
    application.state.session_factory = build_session_factory(engine)
    photo_storage = SupabasePhotoStorage(settings)
    application.state.photo_storage = photo_storage
    sweeper_task: asyncio.Task[None] | None = None
    sweeper_stop: asyncio.Event | None = None
    if settings.sweeper_enabled:
        sweeper_task, sweeper_stop = start_sweeper(
            application.state.session_factory,
            interval_seconds=settings.sweeper_interval_seconds,
        )
    try:
        yield
    finally:
        if sweeper_stop is not None:
            sweeper_stop.set()
        if sweeper_task is not None:
            sweeper_task.cancel()
            with suppress(asyncio.CancelledError):
                await sweeper_task
        await photo_storage.close()
        await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the Sthalo API application."""
    resolved = settings or get_settings()
    configure_logging(resolved)

    docs_enabled = resolved.env.value in {"local", "test"}
    application = FastAPI(
        title="Sthalo API",
        version=__version__,
        debug=resolved.debug,
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    application.state.settings = resolved

    application.add_middleware(RateLimitMiddleware, settings=resolved)
    application.add_middleware(SecurityHeadersMiddleware, settings=resolved)
    application.add_middleware(RequestIDMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            REQUEST_ID_HEADER,
        ],
        expose_headers=[REQUEST_ID_HEADER],
        max_age=600,
    )

    register_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(api_v1_router)
    return application


app = create_app()
