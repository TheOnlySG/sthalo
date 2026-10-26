"""JWKS token verification tests with locally generated ES256 keys."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.config import Settings
from app.integrations.auth.jwks import JwksCache
from app.integrations.auth.verifier import (
    JWTVerifier,
    TokenVerificationError,
)

ISSUER = "http://127.0.0.1:54321/auth/v1"
AUDIENCE = "authenticated"
KID = "unit-key"
PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
PUBLIC_JWK: dict[str, Any] = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(PRIVATE_KEY.public_key()))
PUBLIC_JWK.update({"kid": KID, "alg": "ES256", "use": "sig", "key_ops": ["verify"]})


def settings() -> Settings:
    return Settings(
        _env_file=None,
        env="test",
        database_url="postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/sthalo_test",
        supabase_url="http://127.0.0.1:54321",
        supabase_anon_key="test-anon-key",
        supabase_service_role_key="test-service-role-key",
        supabase_jwks_url=f"{ISSUER}/.well-known/jwks.json",
        supabase_jwt_issuer=ISSUER,
        supabase_jwt_audience=AUDIENCE,
        cors_origins=["http://localhost:5173"],
        log_level="WARNING",
    )


def token(
    subject: UUID,
    *,
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    expires_in: int = 3600,
    role: str = "authenticated",
    kid: str = KID,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject),
        "aud": audience,
        "iss": issuer,
        "role": role,
        "email": "person@example.invalid",
        "exp": now + timedelta(seconds=expires_in),
        "iat": now,
        "user_metadata": {"full_name": "Test Person"},
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm="ES256", headers={"kid": kid})


def verifier(fetch_calls: list[int] | None = None) -> JWTVerifier:
    async def fetch() -> dict[str, Any]:
        if fetch_calls is not None:
            fetch_calls[0] += 1
        return {"keys": [PUBLIC_JWK]}

    return JWTVerifier(settings(), JwksCache("http://test.invalid/jwks", fetch=fetch))


@pytest.mark.asyncio
async def test_valid_token_returns_trusted_claims() -> None:
    subject = uuid4()
    claims = await verifier().verify(token(subject))

    assert claims.subject == subject
    assert claims.email == "person@example.invalid"
    assert claims.full_name == "Test Person"


@pytest.mark.asyncio
async def test_repeated_tokens_reuse_cached_key() -> None:
    calls = [0]
    instance = verifier(calls)
    subject = uuid4()

    await instance.verify(token(subject))
    await instance.verify(token(subject))

    assert calls[0] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("token_value", "reason"),
    [
        ("not-a-token", "malformed"),
        (token(uuid4(), expires_in=-120), "expired"),
        (token(uuid4(), issuer="https://wrong.example/auth/v1"), "wrong_issuer"),
        (token(uuid4(), audience="other-audience"), "wrong_audience"),
        (token(uuid4(), role="anon"), "wrong_role"),
        (token(uuid4(), kid="unknown-key"), "jwks_unavailable"),
    ],
)
async def test_invalid_tokens_are_rejected(token_value: str, reason: str) -> None:
    with pytest.raises(TokenVerificationError) as captured:
        await verifier().verify(token_value)

    assert captured.value.reason == reason


@pytest.mark.asyncio
async def test_token_without_key_id_is_rejected() -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid4()),
        "aud": AUDIENCE,
        "iss": ISSUER,
        "role": "authenticated",
        "exp": now + timedelta(hours=1),
        "iat": now,
    }
    value = jwt.encode(payload, PRIVATE_KEY, algorithm="ES256")

    with pytest.raises(TokenVerificationError, match="missing_key_id"):
        await verifier().verify(value)
