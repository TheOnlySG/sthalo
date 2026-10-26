"""Health endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.main import create_app


def test_liveness_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_lifespan_initializes_database_resources() -> None:
    application = create_app()
    with TestClient(application) as client:
        assert isinstance(application.state.engine, AsyncEngine)
        assert isinstance(application.state.session_factory, async_sessionmaker)
        assert client.get("/health/live").status_code == 200


def test_readiness_returns_ok_when_database_answers(monkeypatch) -> None:
    async def fake_check(_engine: AsyncEngine) -> None:
        return None

    monkeypatch.setattr("app.api.health.check_database_ready", fake_check)
    with TestClient(create_app()) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok"}}


def test_readiness_returns_503_when_database_is_unavailable(monkeypatch) -> None:
    async def failing_check(_engine: AsyncEngine) -> None:
        raise OSError("database is down")

    monkeypatch.setattr("app.api.health.check_database_ready", failing_check)
    with TestClient(create_app()) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "unavailable"},
    }
