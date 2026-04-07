from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.crud import property_crud
from app.deps import (
    CurrentUser,
    can_admin_write,
    can_delete_or_admin,
    can_write_or_admin,
)
from app.limiter import limiter
from app.schemas import (
    PropertyCreate,
    PropertyFilters,
    PropertyListItem,
    PropertyResponse,
    PropertyStatusUpdate,
    PropertyUpdate,
)
from app.scopes import PropertyScope

router = APIRouter(prefix="/properties", tags=["properties"])

DEFAULT_LOCALE = "bg"


@router.get("/")
@limiter.limit("60/minute")
async def list_properties(
    request: Request,
    response: Response,
    filters: PropertyFilters = Depends(),
    lang: str = Query(DEFAULT_LOCALE, max_length=5),
) -> list[PropertyListItem]:
    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=60"
    return await property_crud.list_properties(filters, locale=lang)


@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def create_property(
    request: Request,
    payload: PropertyCreate,
    current_user: CurrentUser = Depends(can_write_or_admin),
):
    return await property_crud.create_property(payload, owner_id=current_user.id)


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
):
    if PropertyScope.ADMIN_WRITE in current_user.scopes:
        property = await property_crud.get_property(property_id)
        if not property:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Property not found"
            )
        property = await property_crud.update_property(
            property_id, payload, owner_id=property.owner_id
        )
    else:
        property = await property_crud.update_property(
            property_id, payload, owner_id=current_user.id
        )

    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found or you don't own it",
        )
    return property


@router.patch(
    "/{property_id}/status",
    response_model=PropertyResponse,
    dependencies=[Depends(can_admin_write)],
)
@limiter.limit("60/minute")
async def update_property_status(request: Request, property_id: UUID, payload: PropertyStatusUpdate):
    property = await property_crud.update_status(property_id, payload)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Property not found"
        )
    return property


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_property(
    request: Request,
    property_id: UUID,
    current_user: CurrentUser = Depends(can_delete_or_admin),
):
    if PropertyScope.ADMIN_DELETE in current_user.scopes:
        deleted = await property_crud.admin_delete_property(property_id)
    else:
        deleted = await property_crud.delete_property(property_id, owner_id=current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found or you don't own it",
        )
