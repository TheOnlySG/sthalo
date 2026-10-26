"""Alembic migration environment for the async Sthalo database."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.db import models as _models  # noqa: F401
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
target_metadata = Base.metadata


def _connect_args() -> dict[str, Any]:
    return {
        "prepared_statement_cache_size": 0,
        "statement_cache_size": 0,
        "server_settings": {
            "application_name": "sthalo-alembic",
            "search_path": "sthalo,public,extensions",
        },
    }


def _configure(connection: Connection | None = None, *, offline: bool = False) -> None:
    options: dict[str, Any] = {
        "target_metadata": target_metadata,
        "include_schemas": True,
        "compare_type": True,
        "version_table_schema": "sthalo",
    }
    if offline:
        options.update(
            {
                "url": settings.database_url,
                "literal_binds": True,
                "dialect_opts": {"paramstyle": "named"},
            }
        )
    else:
        options["connection"] = connection
    context.configure(**options)


def run_migrations_offline() -> None:
    """Emit migration SQL without connecting to the database."""
    _configure(offline=True)
    with context.begin_transaction():
        context.execute("CREATE SCHEMA IF NOT EXISTS sthalo")
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    _configure(connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations through an async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.database_url
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=_connect_args(),
    )
    async with connectable.connect() as connection:
        await connection.execute(text("CREATE SCHEMA IF NOT EXISTS sthalo"))
        await connection.commit()
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
