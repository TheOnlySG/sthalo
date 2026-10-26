"""Database-backed profile, auth, and owner-terms tests."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.errors import AppError, ErrorCode
from app.integrations.auth.verifier import TokenClaims
from app.modules.identity.dependencies import get_admin_user, require_verified_email
from app.modules.identity.models import User


def auth_headers(token_for: Callable[..., str], user: Any) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for(user)}"}


def test_auth_trigger_provisions_profile(
    auth_user_factory: Callable[..., Any],
    db_fetchrow: Callable[..., Any],
) -> None:
    user = auth_user_factory(full_name="Trigger Person")

    row = db_fetchrow(
        "SELECT email, full_name, status FROM sthalo.users WHERE id = $1",
        user.id,
    )

    assert row is not None
    assert row["email"] == user.email
    assert row["full_name"] == "Trigger Person"
    assert row["status"] == "active"


def test_get_me_provisions_a_missing_profile(
    client: TestClient,
    auth_user_factory: Callable[..., Any],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    user = auth_user_factory(full_name="Defensive Profile")
    db_execute("DELETE FROM sthalo.users WHERE id = $1", user.id)

    response = client.get("/api/v1/users/me", headers=auth_headers(token_for, user))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["full_name"] == "Defensive Profile"
    assert body["owner_terms_version"] is None


def test_get_me_requires_a_token(client: TestClient) -> None:
    response = client.get("/api/v1/users/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize(
    "token_options",
    [
        {"expires_in": -120},
        {"issuer": "https://wrong.example/auth/v1"},
        {"audience": "other-audience"},
        {"kid": "unknown-key"},
        {"role": "anon"},
    ],
)
def test_invalid_tokens_are_rejected(
    client: TestClient,
    auth_user_factory: Callable[..., Any],
    token_for: Callable[..., str],
    token_options: dict[str, object],
) -> None:
    user = auth_user_factory()
    token = token_for(user, **token_options)

    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_patch_profile_updates_name_and_phone(
    client: TestClient,
    auth_user_factory: Callable[..., Any],
    token_for: Callable[..., str],
) -> None:
    user = auth_user_factory(full_name="Old Name")

    response = client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token_for, user),
        json={"full_name": "  New   Name  ", "phone": "+91 98765-43210"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["full_name"] == "New Name"
    assert body["phone"] == "+919876543210"


def test_patch_profile_rejects_null_name(
    client: TestClient,
    auth_user_factory: Callable[..., Any],
    token_for: Callable[..., str],
) -> None:
    user = auth_user_factory()

    response = client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token_for, user),
        json={"full_name": None},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_patch_profile_rejects_bad_phone(
    client: TestClient,
    auth_user_factory: Callable[..., Any],
    token_for: Callable[..., str],
) -> None:
    user = auth_user_factory()

    response = client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token_for, user),
        json={"phone": "not-a-phone"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_accept_owner_terms_is_idempotent(
    client: TestClient,
    auth_user_factory: Callable[..., Any],
    token_for: Callable[..., str],
) -> None:
    user = auth_user_factory()
    headers = auth_headers(token_for, user)

    first = client.post("/api/v1/users/me/accept-owner-terms", headers=headers)
    second = client.post("/api/v1/users/me/accept-owner-terms", headers=headers)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    first_body = first.json()
    second_body = second.json()
    assert first_body["owner_terms_version"] == "2026-10-26"
    assert first_body["owner_terms_accepted_at"] == second_body["owner_terms_accepted_at"]


def test_suspended_user_is_forbidden(
    client: TestClient,
    auth_user_factory: Callable[..., Any],
    token_for: Callable[..., str],
    db_execute: Callable[..., str],
) -> None:
    user = auth_user_factory()
    db_execute("UPDATE sthalo.users SET status = 'suspended' WHERE id = $1", user.id)

    response = client.get("/api/v1/users/me", headers=auth_headers(token_for, user))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_verified_dependency_checks_supabase_confirmation(
    client: TestClient,
    auth_user_factory: Callable[..., Any],
) -> None:
    confirmed = auth_user_factory(full_name="Confirmed Person")
    unconfirmed = auth_user_factory(full_name="Unconfirmed Person", confirmed=False)

    async def check() -> None:
        factory = client.app.state.session_factory
        async with factory() as session:
            claims = TokenClaims(
                subject=confirmed.id,
                email=confirmed.email,
                full_name=confirmed.full_name,
            )
            assert await require_verified_email(claims, session) == claims

            unconfirmed_claims = TokenClaims(
                subject=unconfirmed.id,
                email=unconfirmed.email,
                full_name=unconfirmed.full_name,
            )
            with pytest.raises(AppError) as captured:
                await require_verified_email(unconfirmed_claims, session)
            assert captured.value.code == ErrorCode.FORBIDDEN

    asyncio.run(check())


def test_admin_dependency_never_trusts_roles() -> None:
    user_id = UUID("11111111-1111-1111-1111-111111111111")
    normal_user = User(
        id=user_id,
        email="person@example.invalid",
        full_name="Normal User",
        is_admin=False,
        status="active",
    )
    admin_user = User(
        id=user_id,
        email="admin@example.invalid",
        full_name="Admin User",
        is_admin=True,
        status="active",
    )

    with pytest.raises(AppError) as captured:
        asyncio.run(get_admin_user(normal_user))
    assert captured.value.code == ErrorCode.FORBIDDEN
    assert asyncio.run(get_admin_user(admin_user)) is admin_user
