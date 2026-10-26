"""Request-scoped database dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def get_engine(request: Request) -> AsyncEngine:
    """Return the engine configured by the application lifespan."""
    engine = getattr(request.app.state, "engine", None)
    if not isinstance(engine, AsyncEngine):
        raise RuntimeError("Database engine is not configured")
    return engine


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    """Return the session factory configured by the application lifespan."""
    factory = getattr(request.app.state, "session_factory", None)
    if not isinstance(factory, async_sessionmaker):
        raise RuntimeError("Database session factory is not configured")
    return factory


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped session without committing implicitly.

    Services own transaction boundaries. The session is rolled back when the
    request raises and closed when the request completes.
    """
    factory = get_session_factory(request)
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
