"""Fixtures for database-backed V1 API integration tests."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.integrations.auth.jwks import JwksCache
from app.integrations.storage.dependencies import get_photo_storage
from app.main import create_app
from app.modules.identity.dependencies import get_jwks_cache

DATABASE_URL = os.environ["DATABASE_URL"]
PG_DSN = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
ISSUER = "http://127.0.0.1:54321/auth/v1"
AUDIENCE = "authenticated"
KID = "test-signing-key"

PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
PUBLIC_JWK: dict[str, Any] = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(PRIVATE_KEY.public_key()))
PUBLIC_JWK.update({"kid": KID, "alg": "ES256", "use": "sig", "key_ops": ["verify"]})


@dataclass(frozen=True, slots=True)
class TestUser:
    __test__ = False

    id: UUID
    email: str
    full_name: str


class FakePhotoStorage:
    """In-memory replacement for Supabase Storage in API tests."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.fail_uploads = False
        self.fail_signs = False

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        if self.fail_uploads:
            from app.integrations.storage.supabase import PhotoStorageError

            raise PhotoStorageError("forced upload failure")
        self.objects[key] = data
        del content_type

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def signed_url(self, key: str, expires_in: int = 3600) -> str:
        if self.fail_signs:
            from app.integrations.storage.supabase import PhotoStorageError

            raise PhotoStorageError("forced signing failure")
        del expires_in
        return f"http://storage.test/{key}?token=test"


async def _fetch_jwks() -> dict[str, Any]:
    return {"keys": [PUBLIC_JWK]}


async def _execute(query: str, *args: object) -> str:
    connection = await asyncpg.connect(PG_DSN)
    try:
        return await connection.execute(query, *args)
    finally:
        await connection.close()


async def _fetchrow(query: str, *args: object) -> asyncpg.Record | None:
    connection = await asyncpg.connect(PG_DSN)
    try:
        return await connection.fetchrow(query, *args)
    finally:
        await connection.close()


async def _fetchval(query: str, *args: object) -> object:
    connection = await asyncpg.connect(PG_DSN)
    try:
        return await connection.fetchval(query, *args)
    finally:
        await connection.close()


@pytest.fixture(scope="session", autouse=True)
def ensure_test_database() -> None:
    async def prepare() -> None:
        connection = await asyncpg.connect(PG_DSN)
        try:
            await connection.execute(
                """
                CREATE SCHEMA IF NOT EXISTS auth;
                CREATE TABLE IF NOT EXISTS auth.users (
                    id uuid PRIMARY KEY,
                    email text,
                    raw_user_meta_data jsonb NOT NULL DEFAULT '{}'::jsonb,
                    email_confirmed_at timestamptz
                );
                """
            )
            users_table = await connection.fetchval("SELECT to_regclass('sthalo.users')")
            if users_table is None:
                raise RuntimeError("Run `alembic upgrade head` against the test database first")
            trigger = await connection.fetchval(
                "SELECT 1 FROM pg_trigger "
                "WHERE tgrelid = 'auth.users'::regclass "
                "AND tgname = 'trg_auth_users_create_profile'"
            )
            if trigger is None:
                raise RuntimeError("The auth profile trigger is missing; run Alembic migrations")
        finally:
            await connection.close()

    asyncio.run(prepare())


@pytest.fixture(scope="session")
def jwks_cache() -> JwksCache:
    return JwksCache("http://test.invalid/jwks.json", fetch=_fetch_jwks)


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return Settings(
        _env_file=None,
        env="test",
        debug=False,
        log_level="WARNING",
        log_json=False,
        database_url=DATABASE_URL,
        supabase_url="http://127.0.0.1:54321",
        supabase_anon_key="test-anon-key",
        supabase_service_role_key="test-service-role-key",
        supabase_jwks_url=f"{ISSUER}/.well-known/jwks.json",
        supabase_jwt_issuer=ISSUER,
        supabase_jwt_audience=AUDIENCE,
        cors_origins=["http://localhost:5173"],
        sweeper_enabled=True,
        allow_sweeper_disabled=False,
    )


@pytest.fixture
def photo_storage() -> FakePhotoStorage:
    return FakePhotoStorage()


@pytest.fixture
def client(
    test_settings: Settings,
    jwks_cache: JwksCache,
    photo_storage: FakePhotoStorage,
) -> Iterator[TestClient]:
    application = create_app(test_settings)
    application.dependency_overrides[get_jwks_cache] = lambda: jwks_cache
    application.dependency_overrides[get_photo_storage] = lambda: photo_storage
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture
def db_execute() -> Callable[..., str]:
    def execute(query: str, *args: object) -> str:
        return asyncio.run(_execute(query, *args))

    return execute


@pytest.fixture
def db_fetchrow() -> Callable[..., asyncpg.Record | None]:
    def fetchrow(query: str, *args: object) -> asyncpg.Record | None:
        return asyncio.run(_fetchrow(query, *args))

    return fetchrow


@pytest.fixture
def db_fetchval() -> Callable[..., object]:
    def fetchval(query: str, *args: object) -> object:
        return asyncio.run(_fetchval(query, *args))

    return fetchval


@pytest.fixture
def auth_user_factory(
    db_execute: Callable[..., str],
) -> Iterator[Callable[..., TestUser]]:
    created: list[UUID] = []

    def create(
        *,
        email: str | None = None,
        full_name: str = "Test Person",
        confirmed: bool = True,
    ) -> TestUser:
        user_id = uuid4()
        user_email = email or f"user-{user_id}@example.invalid"
        confirmed_at = datetime.now(UTC) if confirmed else None
        db_execute(
            "INSERT INTO auth.users (id, email, raw_user_meta_data, email_confirmed_at) "
            "VALUES ($1, $2, $3::jsonb, $4)",
            user_id,
            user_email,
            json.dumps({"full_name": full_name}),
            confirmed_at,
        )
        created.append(user_id)
        return TestUser(id=user_id, email=user_email, full_name=full_name)

    yield create

    for user_id in created:
        db_execute("DELETE FROM auth.users WHERE id = $1", user_id)


def make_token(
    user: TestUser,
    *,
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    expires_in: int = 3600,
    kid: str = KID,
    role: str = "authenticated",
    key: ec.EllipticCurvePrivateKey = PRIVATE_KEY,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "aud": audience,
        "iss": issuer,
        "role": role,
        "email": user.email,
        "exp": now + timedelta(seconds=expires_in),
        "iat": now,
        "user_metadata": {"full_name": user.full_name},
    }
    return jwt.encode(payload, key, algorithm="ES256", headers={"kid": kid})


@pytest.fixture
def token_for() -> Callable[..., str]:
    return make_token
