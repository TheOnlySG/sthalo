"""Supabase access-token verification against the project JWKS."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import jwt

from app.core.config import Settings
from app.integrations.auth.jwks import SUPPORTED_ALGORITHMS, JwksCache, JwksError


class TokenVerificationError(Exception):
    """A token is missing, expired, malformed, or has invalid claims."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """The small, trusted subset of token claims used by the application."""

    subject: UUID
    email: str | None
    full_name: str | None


def _metadata_name(payload: dict[str, object]) -> str | None:
    metadata = payload.get("user_metadata")
    if not isinstance(metadata, dict):
        return None
    for key in ("full_name", "name"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


class JWTVerifier:
    """Verify Supabase signatures and claims, then expose a trusted subject."""

    def __init__(self, settings: Settings, jwks: JwksCache) -> None:
        self._issuer = settings.supabase_jwt_issuer
        self._audience = settings.supabase_jwt_audience
        self._jwks = jwks

    async def verify(self, token: str) -> TokenClaims:
        if not token or token.count(".") != 2:
            raise TokenVerificationError("malformed")

        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenVerificationError("malformed_header") from exc

        algorithm = header.get("alg")
        kid = header.get("kid")
        if not isinstance(algorithm, str) or algorithm not in SUPPORTED_ALGORITHMS:
            raise TokenVerificationError("unsupported_algorithm")
        if not isinstance(kid, str) or not kid:
            raise TokenVerificationError("missing_key_id")

        try:
            key = await self._jwks.get(kid)
        except JwksError as exc:
            raise TokenVerificationError("jwks_unavailable") from exc

        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=[algorithm],
                audience=self._audience,
                issuer=self._issuer,
                leeway=30,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenVerificationError("expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise TokenVerificationError("wrong_audience") from exc
        except jwt.InvalidIssuerError as exc:
            raise TokenVerificationError("wrong_issuer") from exc
        except jwt.PyJWTError as exc:
            raise TokenVerificationError("invalid_signature_or_claims") from exc

        if payload.get("role") != "authenticated":
            raise TokenVerificationError("wrong_role")

        raw_subject = payload.get("sub")
        if not isinstance(raw_subject, str):
            raise TokenVerificationError("missing_subject")
        try:
            subject = UUID(raw_subject)
        except ValueError as exc:
            raise TokenVerificationError("invalid_subject") from exc

        email = payload.get("email")
        return TokenClaims(
            subject=subject,
            email=email if isinstance(email, str) and email.strip() else None,
            full_name=_metadata_name(payload),
        )
