"""Vehicle management endpoints for the authenticated user."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.db.session import get_session
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User
from app.modules.profiles.schemas import VehicleCreate, VehicleRead, VehicleUpdate
from app.modules.profiles.service import (
    create_vehicle,
    delete_vehicle,
    list_vehicles,
    update_vehicle,
)

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("", response_model=list[VehicleRead])
async def get_vehicles(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[VehicleRead]:
    vehicles = await list_vehicles(session, user)
    return [VehicleRead.model_validate(vehicle) for vehicle in vehicles]


@router.post("", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
async def post_vehicle(
    payload: VehicleCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VehicleRead:
    vehicle = await create_vehicle(session, user, payload)
    return VehicleRead.model_validate(vehicle)


@router.patch("/{vehicle_id}", response_model=VehicleRead)
async def patch_vehicle(
    vehicle_id: UUID,
    payload: VehicleUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VehicleRead:
    values = payload.model_dump(exclude_unset=True)
    for field in ("vehicle_type", "is_ev"):
        if field in values and values[field] is None:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "Request validation failed.",
                status_code=422,
                details=[
                    {
                        "field": field,
                        "message": f"{field} cannot be null",
                        "type": "value_error",
                    }
                ],
            )
    vehicle = await update_vehicle(session, user, vehicle_id, values)
    return VehicleRead.model_validate(vehicle)


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_vehicle(
    vehicle_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await delete_vehicle(session, user, vehicle_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
