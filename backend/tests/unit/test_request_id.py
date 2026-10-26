"""Request ID and CORS tests."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.main import create_app


def test_incoming_request_id_is_echoed() -> None:
    client = TestClient(create_app())
    response = client.get("/health/live", headers={"X-Request-ID": "client-trace-1"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "client-trace-1"


def test_invalid_request_id_is_replaced() -> None:
    client = TestClient(create_app())
    response = client.get("/health/live", headers={"X-Request-ID": "unsafe id"})

    request_id = response.headers["X-Request-ID"]
    assert request_id != "unsafe id"
    assert re.fullmatch(r"[0-9a-f]{32}", request_id)


def test_request_id_is_present_on_errors() -> None:
    client = TestClient(create_app())
    response = client.get("/missing", headers={"X-Request-ID": "error-trace"})

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "error-trace"


def test_cors_allows_configured_origin() -> None:
    client = TestClient(create_app())
    response = client.options(
        "/health/live",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-credentials" not in response.headers


def test_cors_rejects_unknown_origin() -> None:
    client = TestClient(create_app())
    response = client.options(
        "/health/live",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers
