import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.crud import property_crud, property_image_crud, property_translation_crud
from app.deps import (
    CurrentUser,
    NotificationsClient,
    PaymentsClient,
    UsersClient,
    can_admin_write,
    can_delete_or_admin,
    can_write_or_admin,
    get_notifications_client,
    get_payments_client,
    get_users_client,
)
from app.limiter import limiter
from app.schemas import (
    PropertyCreate,
    PropertyFilters,
    PropertyListItem,
    PropertyResponse,
    PropertyStatus,
    PropertyStatusUpdate,
    PropertyUpdate,
)
from app.scopes import PropertyScope
from app.settings import DEFAULT_LOCALE

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("/items/")
async def read_items(filter_query: Annotated[PropertyFilters, Query()]):
    return filter_query


@router.get("/")
@limiter.limit("60/minute")
async def list_properties(
    request: Request,
    response: Response,
    filters: PropertyFilters = Query(),
) -> list[PropertyListItem]:
    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=60"
    return await property_crud.list_properties(filters, locale=filters.lang)


@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def create_property(
    request: Request,
    payload: PropertyCreate,
    current_user: CurrentUser = Depends(can_write_or_admin),
    payments_client: PaymentsClient = Depends(get_payments_client),
):
    if not current_user.is_admin:
        current_count = await property_crud.count_by_owner(current_user.id)
        allowed = await payments_client.can_add_listing(current_user.id, current_count)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Active subscription required to add listings. Upgrade your plan.",
            )
    created = await property_crud.create_property(payload, owner_id=current_user.id)

    for tr in payload.translations:
        await property_translation_crud.create_for_property(created.id, tr)
    for img in payload.images:
        await property_image_crud.create_for_property(created.id, img)

    if payload.translations or payload.images:
        return await property_crud.get_property(created.id)
    return created


@router.get("/bulk", response_model=list[PropertyListItem])
@limiter.limit("500/minute")
async def get_properties_bulk(
    request: Request,
    ids: list[UUID] = Query(..., min_length=1),
    lang: str = Query(DEFAULT_LOCALE, max_length=5),
) -> list[PropertyListItem]:
    return await property_crud.get_properties_by_ids(ids, locale=lang)


@router.get(
    "/{property_id}",
    response_model=PropertyResponse,
)
@limiter.limit("60/minute")
async def get_property(request: Request, property_id: UUID, response: Response):
    property = await property_crud.get_property(property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Property not found"
        )
    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=120"
    return property


@router.patch("/{property_id}", response_model=PropertyResponse)
@limiter.limit("60/minute")
async def update_property(
    request: Request,
    property_id: UUID,
    payload: PropertyUpdate,
    current_user: CurrentUser = Depends(can_write_or_admin),
    payments_client: PaymentsClient = Depends(get_payments_client),
):
    is_admin = (
        PropertyScope.ADMIN_WRITE in current_user.scopes
        or PropertyScope.ADMIN in current_user.scopes
    )

    if payload.payment_config is not None and not is_admin:
        caps = await payments_client.get_payment_capabilities()
        methods = payload.payment_config.accepted_methods
        if "card" in methods and not caps.get("can_accept_card"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Card payments require an active Stripe Connect account with no outstanding requirements.",
            )
        if "bank_transfer" in methods and not caps.get("can_accept_bank_transfer"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bank transfer payments require a bank account to be configured.",
            )

    updated = await property_crud.update_property(
        property_id, payload, owner_id=None if is_admin else current_user.id
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found or you don't own it",
        )

    if payload.images is not None:
        await property_image_crud.replace_for_property(property_id, payload.images)
    if payload.translations is not None:
        await property_translation_crud.upsert_for_property(
            property_id, payload.translations
        )

    if payload.images is not None or payload.translations is not None:
        return await property_crud.get_property(property_id)
    return updated


@router.patch(
    "/{property_id}/status",
    response_model=PropertyResponse,
)
@limiter.limit("60/minute")
async def update_property_status(
    request: Request,
    property_id: UUID,
    payload: PropertyStatusUpdate,
    _: CurrentUser = Depends(can_admin_write),
    users_client: UsersClient = Depends(get_users_client),
    notifications_client: NotificationsClient = Depends(get_notifications_client),
):
    property = await property_crud.update_status(property_id, payload)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Property not found"
        )

    if payload.status == PropertyStatus.ACTIVE:
        asyncio.create_task(
            _notify_property_approved(property, users_client, notifications_client)
        )

    return property


async def _notify_property_approved(
    property, users_client: UsersClient, nc: NotificationsClient
) -> None:
    owner_email, owner_locale = await users_client.get_email_and_locale(
        property.owner_id
    )
    if not owner_email:
        return
    await nc.send(
        to=owner_email,
        notification_type="property_approved",
        locale=owner_locale,
    )


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_property(
    request: Request,
    property_id: UUID,
    current_user: CurrentUser = Depends(can_delete_or_admin),
):
    is_admin = (
        PropertyScope.ADMIN_DELETE in current_user.scopes
        or PropertyScope.ADMIN in current_user.scopes
    )
    if is_admin:
        deleted = await property_crud.admin_delete_property(property_id)
    else:
        deleted = await property_crud.delete_property(
            property_id, owner_id=current_user.id
        )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found or you don't own it",
        )
