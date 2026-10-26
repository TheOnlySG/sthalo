"""Async database engine and session factory construction."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings

APPLICATION_NAME = "sthalo-api"
SEARCH_PATH = "sthalo,public,extensions"


def _connect_args(application_name: str) -> dict[str, Any]:
    return {
        "prepared_statement_cache_size": 0,
        "statement_cache_size": 0,
        "server_settings": {
            "application_name": application_name,
            "search_path": SEARCH_PATH,
        },
    }


def build_engine(settings: Settings, *, application_name: str = APPLICATION_NAME) -> AsyncEngine:
    """Build an async engine with pooler-safe settings.

    Prepared-statement caching is disabled because the hosted database uses the
    Supabase transaction pooler. The search path keeps application objects and
    PostGIS types reachable without schema-qualifying every query.
    """
    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_size=5,
        max_overflow=5,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
        connect_args=_connect_args(application_name),
    )


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create the configured async session factory."""
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
