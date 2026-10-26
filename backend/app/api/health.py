"""Liveness and readiness endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.health import check_database_ready

router = APIRouter(tags=["health"])
_logger = structlog.get_logger("sthalo.health")


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: Literal["ok", "not_ready"]
    checks: dict[str, str]


def get_app_engine(request: Request) -> AsyncEngine:
    engine = getattr(request.app.state, "engine", None)
    if not isinstance(engine, AsyncEngine):
        raise RuntimeError("Database engine is not configured")
    return engine


@router.get("/health/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """Report that the process can serve requests."""
    return HealthResponse()


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse, "description": "Database unavailable"}},
)
async def readiness(
    response: Response,
    engine: Annotated[AsyncEngine, Depends(get_app_engine)],
) -> ReadinessResponse:
    """Report whether the database and Alembic baseline are ready."""
    try:
        await check_database_ready(engine)
    except Exception as exc:
        _logger.warning("database_unavailable", error_type=type(exc).__name__)
        response.status_code = 503
        return ReadinessResponse(status="not_ready", checks={"database": "unavailable"})
    return ReadinessResponse(status="ok", checks={"database": "ok"})
