from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.crud import assert_owns_property, property_translation_crud
from app.deps import (
    CurrentUser,
    can_write_or_admin,
)
from app.limiter import limiter
from app.schemas import (
    TranslationCreate,
    TranslationResponse,
    TranslationUpdate,
)

router = APIRouter(
    prefix="/properties/{property_id}/translations", tags=["Property Translations"]
)


@router.get("", response_model=list[TranslationResponse])
@limiter.limit("60/minute")
async def list_translations(request: Request, property_id: UUID):
    return await property_translation_crud.list_for_property(property_id)


@router.post(
    "",
    response_model=TranslationResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("60/minute")
async def add_translation(
    request: Request,
    property_id: UUID,
    payload: TranslationCreate,
    current_user: CurrentUser = Depends(can_write_or_admin),
):
    await assert_owns_property(property_id, current_user)
    return await property_translation_crud.create_for_property(property_id, payload)


@router.patch("/{locale}", response_model=TranslationResponse)
@limiter.limit("60/minute")
async def update_translation(
    request: Request,
    property_id: UUID,
    locale: str,
    payload: TranslationUpdate,
    current_user: CurrentUser = Depends(can_write_or_admin),
):
    await assert_owns_property(property_id, current_user)
    item = await property_translation_crud.update(property_id, locale, payload)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Translation for locale '{locale}' not found",
        )
    return item


@router.delete("/{locale}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_translation(
    request: Request,
    property_id: UUID,
    locale: str,
    current_user: CurrentUser = Depends(can_write_or_admin),
):
    await assert_owns_property(property_id, current_user)
    deleted = await property_translation_crud.delete(property_id, locale)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Translation for locale '{locale}' not found",
        )
