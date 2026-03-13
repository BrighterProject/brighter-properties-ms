from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.crud import assert_owns_property, property_unavailability_crud
from app.deps import (
    CurrentUser,
    can_schedule_or_admin,
)
from app.schemas import (
    PropertyUnavailabilityCreate,
    PropertyUnavailabilityResponse,
    PropertyUnavailabilityUpdate,
)

router = APIRouter(
    prefix="/properties/{property_id}/unavailabilities", tags=["Property Unavailabilities"]
)


@router.get("", response_model=list[PropertyUnavailabilityResponse])
async def list_unavailabilities(property_id: UUID):
    return await property_unavailability_crud.list_for_property(property_id)


@router.post(
    "",
    response_model=PropertyUnavailabilityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_unavailability(
    property_id: UUID,
    payload: PropertyUnavailabilityCreate,
    current_user: CurrentUser = Depends(can_schedule_or_admin),
):
    await assert_owns_property(property_id, current_user)
    return await property_unavailability_crud.create_for_property(property_id, payload)


@router.patch("/{unavailability_id}", response_model=PropertyUnavailabilityResponse)
async def update_unavailability(
    property_id: UUID,
    unavailability_id: UUID,
    payload: PropertyUnavailabilityUpdate,
    current_user: CurrentUser = Depends(can_schedule_or_admin),
):
    await assert_owns_property(property_id, current_user)
    item = await property_unavailability_crud.update(unavailability_id, property_id, payload)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unavailability not found"
        )
    return item


@router.delete("/{unavailability_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unavailability(
    property_id: UUID,
    unavailability_id: UUID,
    current_user: CurrentUser = Depends(can_schedule_or_admin),
):
    await assert_owns_property(property_id, current_user)
    deleted = await property_unavailability_crud.delete(unavailability_id, property_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unavailability not found"
        )
