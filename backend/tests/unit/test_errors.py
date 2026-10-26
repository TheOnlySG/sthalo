"""Error envelope and handler tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.errors import AppError, ErrorCode
from app.main import create_app


def test_not_found_uses_error_envelope_and_request_id() -> None:
    client = TestClient(create_app())
    response = client.get("/missing", headers={"X-Request-ID": "trace-404"})

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "trace-404"
    payload = response.json()
    assert payload["error"]["code"] == "NOT_FOUND"
    assert payload["error"]["message"] == "Not Found"
    assert payload["error"]["details"] == []
    assert payload["error"]["request_id"] == "trace-404"


def test_app_error_preserves_code_status_details_and_headers() -> None:
    application = create_app()

    @application.get("/_test/app-error")
    async def raise_app_error() -> None:
        raise AppError(
            ErrorCode.SLOT_UNAVAILABLE,
            "That time is no longer available.",
            status_code=409,
            details=[{"field": "time_range", "reason": "overlap"}],
            headers={"Retry-After": "5"},
        )

    client = TestClient(application)
    response = client.get("/_test/app-error", headers={"X-Request-ID": "trace-409"})

    assert response.status_code == 409
    assert response.headers["Retry-After"] == "5"
    assert response.headers["X-Request-ID"] == "trace-409"
    payload = response.json()
    assert payload["error"]["code"] == "SLOT_UNAVAILABLE"
    assert payload["error"]["message"] == "That time is no longer available."
    assert payload["error"]["details"] == [{"field": "time_range", "reason": "overlap"}]
    assert payload["error"]["request_id"] == "trace-409"


def test_validation_error_uses_validation_envelope() -> None:
    application = create_app()

    @application.get("/_test/validate")
    async def validate(limit: int) -> dict[str, int]:
        return {"limit": limit}

    client = TestClient(application)
    response = client.get("/_test/validate", headers={"X-Request-ID": "trace-422"})

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["message"] == "Request validation failed."
    assert payload["error"]["request_id"] == "trace-422"
    assert payload["error"]["details"]
    assert payload["error"]["details"][0]["field"] == "query.limit"


def test_unhandled_exception_hides_internal_detail() -> None:
    application = create_app()

    @application.get("/_test/unhandled")
    async def raise_unhandled() -> None:
        raise RuntimeError("secret database detail")

    client = TestClient(application, raise_server_exceptions=False)
    response = client.get("/_test/unhandled", headers={"X-Request-ID": "trace-500"})

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "trace-500"
    assert "secret database detail" not in response.text
    payload = response.json()
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert payload["error"]["message"] == "An unexpected error occurred."
    assert payload["error"]["request_id"] == "trace-500"
