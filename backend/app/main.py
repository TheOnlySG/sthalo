"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.request_id import REQUEST_ID_HEADER, RequestIDMiddleware
from app.db.engine import build_engine, build_session_factory


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Create database resources on startup and dispose them on shutdown."""
    settings = application.state.settings
    if not isinstance(settings, Settings):
        raise RuntimeError("Application settings are not configured")
    engine = build_engine(settings)
    application.state.engine = engine
    application.state.session_factory = build_session_factory(engine)
    try:
        yield
    finally:
        await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the Sthalo API application."""
    resolved = settings or get_settings()
    configure_logging(resolved)

    application = FastAPI(
        title="Sthalo API",
        version=__version__,
        debug=resolved.debug,
        lifespan=lifespan,
    )
    application.state.settings = resolved

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
    application.add_middleware(RequestIDMiddleware)

    register_exception_handlers(application)
    application.include_router(health_router)
    return application


app = create_app()
