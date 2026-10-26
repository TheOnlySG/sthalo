"""Environment-backed application settings."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Literal, Self
from urllib.parse import urlparse, urlsplit

from pydantic import Field, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Configuration loaded from environment variables or a local `.env` file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    env: Environment = Environment.LOCAL
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    log_json: bool = False

    database_url: str
    supabase_url: str
    supabase_anon_key: SecretStr
    supabase_service_role_key: SecretStr
    supabase_jwks_url: str
    supabase_jwt_issuer: str
    supabase_jwt_audience: str = "authenticated"

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    sweeper_enabled: bool = True
    allow_sweeper_disabled: bool = False
    sweeper_interval_seconds: int = Field(default=45, ge=5, le=3600)
    max_upload_bytes: int = Field(default=5 * 1024 * 1024, gt=0, le=50 * 1024 * 1024)
    geocode_provider: Literal["none"] = "none"

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError("LOG_LEVEL must be CRITICAL, ERROR, WARNING, INFO, or DEBUG")
        return normalized

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: list[str]) -> list[str]:
        origins: list[str] = []
        for origin in value:
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("CORS_ORIGINS entries must be absolute http(s) origins")
            if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
                raise ValueError("CORS_ORIGINS entries must not contain paths or query strings")
            origins.append(origin.rstrip("/"))
        if not origins:
            raise ValueError("CORS_ORIGINS must contain at least one origin")
        return list(dict.fromkeys(origins))

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg:// scheme")
        parsed = urlsplit(value)
        if not parsed.hostname or parsed.path in {"", "/"}:
            raise ValueError("DATABASE_URL must include a host and database name")
        return value

    @field_validator("supabase_url", "supabase_jwks_url", "supabase_jwt_issuer")
    @classmethod
    def validate_http_url(cls, value: str, info: ValidationInfo) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"{info.field_name} must be an absolute http(s) URL")
        return value.rstrip("/")

    @field_validator("supabase_anon_key", "supabase_service_role_key")
    @classmethod
    def validate_secret_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("Supabase keys must not be empty")
        return value

    @model_validator(mode="after")
    def validate_deployment_settings(self) -> Self:
        if self.env not in {Environment.STAGING, Environment.PRODUCTION}:
            return self

        if self.debug:
            raise ValueError("DEBUG must be false outside local/test")
        if not self.cors_origins:
            raise ValueError("CORS_ORIGINS must be set outside local/test")
        for origin in self.cors_origins:
            parsed = urlparse(origin)
            if parsed.scheme != "https":
                raise ValueError("CORS_ORIGINS must use https outside local/test")
            if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError("CORS_ORIGINS must not contain local hosts outside local/test")

        if not self.supabase_url.startswith("https://"):
            raise ValueError("SUPABASE_URL must use https outside local/test")
        if not self.supabase_jwks_url.startswith("https://"):
            raise ValueError("SUPABASE_JWKS_URL must use https outside local/test")
        if not self.supabase_jwt_issuer.startswith("https://"):
            raise ValueError("SUPABASE_JWT_ISSUER must use https outside local/test")

        for secret in (self.supabase_anon_key, self.supabase_service_role_key):
            value = secret.get_secret_value()
            if len(value) < 32 or value.lower().startswith(("replace-", "ci-")):
                raise ValueError("Supabase keys must be real secrets outside local/test")

        if not self.sweeper_enabled and not self.allow_sweeper_disabled:
            raise ValueError("SWEEPER_ENABLED=false requires ALLOW_SWEEPER_DISABLED=true")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
