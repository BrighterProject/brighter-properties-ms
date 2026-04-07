from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.crud import assert_owns_property, property_image_crud
from app.deps import (
    CurrentUser,
    can_images_or_admin,
)
from app.limiter import limiter
from app.schemas import (
    PropertyImageCreate,
    PropertyImageResponse,
    PropertyImageUpdate,
)

router = APIRouter(prefix="/properties/{property_id}/images", tags=["Property Images"])


@router.get("", response_model=list[PropertyImageResponse])
@limiter.limit("60/minute")
async def list_images(request: Request, property_id: UUID):
    return await property_image_crud.list_for_property(property_id)


@router.post(
    "",
    response_model=PropertyImageResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("60/minute")
async def add_image(
    request: Request,
    property_id: UUID,
    payload: PropertyImageCreate,
    current_user: CurrentUser = Depends(can_images_or_admin),
):
    await assert_owns_property(property_id, current_user)
    return await property_image_crud.create_for_property(property_id, payload)


@router.patch("/{image_id}", response_model=PropertyImageResponse)
@limiter.limit("60/minute")
async def update_image(
    request: Request,
    property_id: UUID,
    image_id: UUID,
    payload: PropertyImageUpdate,
    current_user: CurrentUser = Depends(can_images_or_admin),
):
    await assert_owns_property(property_id, current_user)
    img = await property_image_crud.update(image_id, property_id, payload)
    if not img:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image not found"
        )
    return img


@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_image(
    request: Request,
    property_id: UUID,
    image_id: UUID,
    current_user: CurrentUser = Depends(can_images_or_admin),
):
    await assert_owns_property(property_id, current_user)
    deleted = await property_image_crud.delete(image_id, property_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image not found"
        )


@router.put("/reorder", response_model=list[PropertyImageResponse])
@limiter.limit("60/minute")
async def reorder_images(
    request: Request,
    property_id: UUID,
    ordered_ids: list[UUID],
    current_user: CurrentUser = Depends(can_images_or_admin),
):
    await assert_owns_property(property_id, current_user)
    return await property_image_crud.reorder(property_id, ordered_ids)
