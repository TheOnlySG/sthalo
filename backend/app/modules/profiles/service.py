"""Vehicle CRUD and ownership rules."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.modules.identity.models import User
from app.modules.profiles.models import Vehicle
from app.modules.profiles.schemas import VehicleCreate

MAX_VEHICLES_PER_USER = 10
_logger = structlog.get_logger("sthalo.vehicles")


async def list_vehicles(session: AsyncSession, user: User) -> list[Vehicle]:
    result = await session.scalars(
        select(Vehicle).where(Vehicle.user_id == user.id).order_by(Vehicle.created_at, Vehicle.id)
    )
    return list(result)


async def create_vehicle(
    session: AsyncSession,
    user: User,
    payload: VehicleCreate,
) -> Vehicle:
    count = await session.scalar(
        select(func.count()).select_from(Vehicle).where(Vehicle.user_id == user.id)
    )
    if count is not None and count >= MAX_VEHICLES_PER_USER:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Vehicle limit reached.",
            status_code=422,
            details=[
                {
                    "field": "vehicles",
                    "message": f"At most {MAX_VEHICLES_PER_USER} vehicles are allowed.",
                    "type": "value_error",
                }
            ],
        )

    vehicle = Vehicle(user_id=user.id, **payload.model_dump())
    session.add(vehicle)
    await session.commit()
    await session.refresh(vehicle)
    _logger.info(
        "vehicle_created",
        user_id=str(user.id),
        vehicle_id=str(vehicle.id),
        vehicle_type=vehicle.vehicle_type,
    )
    return vehicle


async def get_owned_vehicle(
    session: AsyncSession,
    user: User,
    vehicle_id: UUID,
) -> Vehicle:
    vehicle = await session.scalar(
        select(Vehicle).where(
            Vehicle.id == vehicle_id,
            Vehicle.user_id == user.id,
        )
    )
    if vehicle is None:
        raise AppError(
            ErrorCode.NOT_FOUND,
            "Vehicle not found.",
            status_code=404,
        )
    return vehicle


async def update_vehicle(
    session: AsyncSession,
    user: User,
    vehicle_id: UUID,
    values: dict[str, Any],
) -> Vehicle:
    vehicle = await get_owned_vehicle(session, user, vehicle_id)
    for field, value in values.items():
        setattr(vehicle, field, value)
    if values:
        await session.commit()
        await session.refresh(vehicle)
        _logger.info(
            "vehicle_updated",
            user_id=str(user.id),
            vehicle_id=str(vehicle.id),
            fields=sorted(values),
        )
    return vehicle


async def delete_vehicle(
    session: AsyncSession,
    user: User,
    vehicle_id: UUID,
) -> None:
    vehicle = await get_owned_vehicle(session, user, vehicle_id)
    await session.delete(vehicle)
    await session.commit()
    _logger.info(
        "vehicle_deleted",
        user_id=str(user.id),
        vehicle_id=str(vehicle.id),
    )
