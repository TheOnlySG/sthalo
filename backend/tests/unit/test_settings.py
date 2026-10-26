"""Settings validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Environment, Settings


def base_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "env": "test",
        "debug": False,
        "log_json": False,
        "sweeper_enabled": True,
        "allow_sweeper_disabled": False,
        "database_url": "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/sthalo_test",
        "supabase_url": "http://127.0.0.1:54321",
        "supabase_anon_key": "test-anon-key",
        "supabase_service_role_key": "test-service-role-key",
        "supabase_jwks_url": "http://127.0.0.1:54321/auth/v1/.well-known/jwks.json",
        "supabase_jwt_issuer": "http://127.0.0.1:54321/auth/v1",
        "cors_origins": "http://localhost:5173",
        "log_level": "WARNING",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_defaults_are_safe_for_local_development() -> None:
    settings = base_settings()
    assert settings.env is Environment.TEST
    assert settings.debug is False
    assert settings.log_json is False
    assert settings.sweeper_enabled is True
    assert settings.sweeper_interval_seconds == 45
    assert settings.max_upload_bytes == 5 * 1024 * 1024
    assert settings.geocode_provider == "none"


def test_cors_origins_accept_comma_separated_values() -> None:
    settings = base_settings(
        cors_origins="https://one.example, https://two.example/, https://one.example"
    )
    assert settings.cors_origins == ["https://one.example", "https://two.example"]


def test_cors_origins_reject_paths() -> None:
    with pytest.raises(ValidationError):
        base_settings(cors_origins="https://one.example/app")


def test_cors_origins_reject_empty_list() -> None:
    with pytest.raises(ValidationError):
        base_settings(cors_origins="")


def test_database_url_must_use_asyncpg() -> None:
    with pytest.raises(ValidationError):
        base_settings(database_url="postgresql://postgres:postgres@127.0.0.1/postgres")


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+asyncpg://",
        "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432",
        "postgresql+asyncpg://postgres:postgres@/postgres",
    ],
)
def test_database_url_must_include_host_and_database(database_url: str) -> None:
    with pytest.raises(ValidationError):
        base_settings(database_url=database_url)


def test_log_level_is_normalized() -> None:
    settings = base_settings(log_level="debug")
    assert settings.log_level == "DEBUG"


def test_log_level_rejects_unknown_values() -> None:
    with pytest.raises(ValidationError):
        base_settings(log_level="verbose")


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "env": "production",
        "cors_origins": "https://app.example",
        "supabase_url": "https://project.supabase.co",
        "supabase_jwks_url": "https://project.supabase.co/auth/v1/.well-known/jwks.json",
        "supabase_jwt_issuer": "https://project.supabase.co/auth/v1",
        "supabase_anon_key": "a" * 40,
        "supabase_service_role_key": "b" * 40,
    }
    values.update(overrides)
    return base_settings(**values)


def test_production_settings_accept_secure_configuration() -> None:
    settings = production_settings()
    assert settings.env is Environment.PRODUCTION
    assert settings.cors_origins == ["https://app.example"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"debug": True},
        {"cors_origins": "http://localhost:5173"},
        {"cors_origins": "http://app.example"},
        {"supabase_url": "http://project.supabase.co"},
        {"supabase_jwks_url": "http://project.supabase.co/jwks.json"},
        {"supabase_jwt_issuer": "http://project.supabase.co/auth/v1"},
        {"supabase_anon_key": "short"},
        {"supabase_service_role_key": "ci-placeholder"},
        {"sweeper_enabled": False},
    ],
)
def test_production_settings_reject_unsafe_configuration(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        production_settings(**overrides)


def test_sweeper_can_be_disabled_with_explicit_override() -> None:
    settings = production_settings(sweeper_enabled=False, allow_sweeper_disabled=True)
    assert settings.sweeper_enabled is False
    assert settings.allow_sweeper_disabled is True
