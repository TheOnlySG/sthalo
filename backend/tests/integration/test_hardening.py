"""Security-header and rate-limit behavior tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_security_headers_cover_api_and_health(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]


def test_rate_limit_returns_429_envelope(
    test_settings: Settings,
) -> None:
    settings = test_settings.model_copy(
        update={
            "rate_limit_enabled": True,
            "rate_limit_default_requests": 2,
            "rate_limit_window_seconds": 60,
        }
    )
    application = create_app(settings)
    with TestClient(application) as limited_client:
        first = limited_client.get("/api/v1/not-a-route")
        second = limited_client.get("/api/v1/not-a-route")
        third = limited_client.get("/api/v1/not-a-route")

    assert first.status_code == 404
    assert second.status_code == 404
    assert third.status_code == 429
    assert third.headers["retry-after"]
    assert third.headers["x-ratelimit-remaining"] == "0"
    body = third.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["request_id"] == third.headers["x-request-id"]
