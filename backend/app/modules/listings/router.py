"""Public, owner, and admin listing endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.dependencies import get_application_settings
from app.db.session import get_session
from app.integrations.storage.dependencies import get_photo_storage
from app.integrations.storage.supabase import PhotoStorage
from app.modules.identity.dependencies import get_admin_user, get_current_user
from app.modules.identity.models import User
from app.modules.listings.models import ListingStatus
from app.modules.listings.schemas import (
    ListingAdminRead,
    ListingCreate,
    ListingOwnerRead,
    ListingOwnerSummary,
    ListingPublicRead,
    ListingSubmit,
    ListingUpdate,
    ModerationAction,
    PhotoPatch,
)
from app.modules.listings.service import (
    add_photo,
    approve_listing,
    archive_listing,
    create_listing,
    delete_photo,
    get_admin_listing,
    get_owner_listing,
    get_public_listing,
    list_admin_listings,
    list_owner_listings,
    pause_listing,
    reject_listing,
    restore_listing,
    resume_listing,
    submit_listing,
    suspend_listing,
    update_listing,
    update_photo,
)

public_router = APIRouter(prefix="/parking-listings", tags=["parking listings"])
owner_router = APIRouter(prefix="/owner/parking-listings", tags=["owner listings"])
admin_router = APIRouter(prefix="/admin/listings", tags=["admin listings"])


@public_router.get("/{listing_id}", response_model=ListingPublicRead)
async def get_public_parking_listing(
    listing_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> ListingPublicRead:
    return await get_public_listing(session, listing_id, storage)


@owner_router.get("", response_model=list[ListingOwnerSummary])
async def get_owner_parking_listings(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> list[ListingOwnerSummary]:
    return await list_owner_listings(session, user, storage)


@owner_router.post(
    "",
    response_model=ListingOwnerRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_owner_parking_listing(
    payload: ListingCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> ListingOwnerRead:
    return await create_listing(session, user, payload, storage)


@owner_router.get("/{listing_id}", response_model=ListingOwnerRead)
async def get_owner_parking_listing(
    listing_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> ListingOwnerRead:
    return await get_owner_listing(session, user, listing_id, storage)


@owner_router.patch("/{listing_id}", response_model=ListingOwnerRead)
async def patch_owner_parking_listing(
    listing_id: UUID,
    payload: ListingUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> ListingOwnerRead:
    return await update_listing(session, user, listing_id, payload, storage)


@owner_router.post("/{listing_id}/submit", response_model=ListingOwnerRead)
async def submit_owner_parking_listing(
    listing_id: UUID,
    payload: ListingSubmit,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> ListingOwnerRead:
    return await submit_listing(
        session,
        user,
        listing_id,
        payload.declaration_accepted,
        storage,
    )


@owner_router.post("/{listing_id}/pause", response_model=ListingOwnerRead)
async def pause_owner_parking_listing(
    listing_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> ListingOwnerRead:
    return await pause_listing(session, user, listing_id, storage)


@owner_router.post("/{listing_id}/resume", response_model=ListingOwnerRead)
async def resume_owner_parking_listing(
    listing_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> ListingOwnerRead:
    return await resume_listing(session, user, listing_id, storage)


@owner_router.post("/{listing_id}/archive", response_model=ListingOwnerRead)
async def archive_owner_parking_listing(
    listing_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> ListingOwnerRead:
    return await archive_listing(session, user, listing_id, storage)


@owner_router.post(
    "/{listing_id}/photos",
    response_model=ListingOwnerRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_owner_listing_photo(
    listing_id: UUID,
    file: Annotated[UploadFile, File()],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
    settings: Annotated[Settings, Depends(get_application_settings)],
) -> ListingOwnerRead:
    raw = await file.read(settings.max_upload_bytes + 1)
    return await add_photo(
        session,
        user,
        listing_id,
        raw,
        max_upload_bytes=settings.max_upload_bytes,
        storage=storage,
    )


@owner_router.patch(
    "/{listing_id}/photos/{photo_id}",
    response_model=ListingOwnerRead,
)
async def patch_owner_listing_photo(
    listing_id: UUID,
    photo_id: UUID,
    payload: PhotoPatch,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> ListingOwnerRead:
    return await update_photo(
        session,
        user,
        listing_id,
        photo_id,
        payload,
        storage,
    )


@owner_router.delete(
    "/{listing_id}/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_owner_listing_photo(
    listing_id: UUID,
    photo_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> Response:
    await delete_photo(session, user, listing_id, photo_id, storage)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.get("", response_model=list[ListingAdminRead])
async def get_admin_parking_listings(
    admin: Annotated[User, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
    listing_status: Annotated[ListingStatus | None, Query(alias="status")] = None,
) -> list[ListingAdminRead]:
    del admin
    return await list_admin_listings(session, listing_status, storage)


@admin_router.get("/{listing_id}", response_model=ListingAdminRead)
async def get_admin_parking_listing(
    listing_id: UUID,
    admin: Annotated[User, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> ListingAdminRead:
    del admin
    return await get_admin_listing(session, listing_id, storage)


@admin_router.post("/{listing_id}/approve", response_model=ListingAdminRead)
async def approve_admin_parking_listing(
    listing_id: UUID,
    payload: ModerationAction,
    admin: Annotated[User, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> ListingAdminRead:
    return await approve_listing(session, admin, listing_id, payload, storage)


@admin_router.post("/{listing_id}/reject", response_model=ListingAdminRead)
async def reject_admin_parking_listing(
    listing_id: UUID,
    payload: ModerationAction,
    admin: Annotated[User, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> ListingAdminRead:
    return await reject_listing(session, admin, listing_id, payload, storage)


@admin_router.post("/{listing_id}/suspend", response_model=ListingAdminRead)
async def suspend_admin_parking_listing(
    listing_id: UUID,
    payload: ModerationAction,
    admin: Annotated[User, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> ListingAdminRead:
    return await suspend_listing(session, admin, listing_id, payload, storage)


@admin_router.post("/{listing_id}/restore", response_model=ListingAdminRead)
async def restore_admin_parking_listing(
    listing_id: UUID,
    payload: ModerationAction,
    admin: Annotated[User, Depends(get_admin_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> ListingAdminRead:
    return await restore_listing(session, admin, listing_id, payload, storage)
