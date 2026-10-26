"""Database readiness checks."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def check_database_ready(engine: AsyncEngine) -> None:
    """Verify the database answers and the Alembic baseline is stamped."""
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
        version = await connection.scalar(
            text("SELECT version_num FROM sthalo.alembic_version LIMIT 1")
        )
    if version is None:
        raise RuntimeError("Database migrations are not applied")
