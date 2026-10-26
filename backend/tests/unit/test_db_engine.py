"""Async engine and session factory tests."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.engine import build_engine, build_session_factory


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        env="test",
        database_url="postgresql+asyncpg://user:pass@127.0.0.1:5432/sthalo_test",
        supabase_url="http://127.0.0.1:54321",
        supabase_anon_key="test-anon-key",
        supabase_service_role_key="test-service-role-key",
        supabase_jwks_url="http://127.0.0.1:54321/auth/v1/.well-known/jwks.json",
        supabase_jwt_issuer="http://127.0.0.1:54321/auth/v1",
        cors_origins="http://localhost:5173",
    )


async def test_engine_is_asyncpg_and_disposes_cleanly() -> None:
    engine = build_engine(_settings())

    assert engine.url.drivername == "postgresql+asyncpg"
    assert engine.url.database == "sthalo_test"
    await engine.dispose()


async def test_session_factory_uses_async_sessions() -> None:
    engine = build_engine(_settings())
    factory = build_session_factory(engine)

    assert isinstance(factory, async_sessionmaker)
    async with factory() as session:
        assert isinstance(session, AsyncSession)
        assert session.sync_session.expire_on_commit is False

    await engine.dispose()
