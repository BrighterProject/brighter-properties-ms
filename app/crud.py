from __future__ import annotations

import json
from uuid import UUID

from fastapi import HTTPException, status
from ms_core import CRUD
from tortoise.exceptions import DoesNotExist

from app.deps import CurrentUser
from app.scopes import PropertyScope

from .models import Property, PropertyImage, PropertyUnavailability
from .schemas import (
    PropertyCreate,
    PropertyFilters,
    PropertyImageCreate,
    PropertyImageResponse,
    PropertyImageUpdate,
    PropertyListItem,
    PropertyResponse,
    PropertyStatus,
    PropertyStatusUpdate,
    PropertyUnavailabilityCreate,
    PropertyUnavailabilityResponse,
    PropertyUnavailabilityUpdate,
    PropertyUpdate,
)


class PropertyImageCRUD(CRUD[PropertyImage, PropertyImageResponse]):  # type: ignore
    async def create_for_property(
        self, property_id: UUID, payload: PropertyImageCreate
    ) -> PropertyImageResponse:
        # If this is marked as thumbnail, demote any existing thumbnails first.
        if payload.is_thumbnail:
            await PropertyImage.filter(property_id=property_id, is_thumbnail=True).update(
                is_thumbnail=False
            )

        inst = await PropertyImage.create(
            property_id=property_id,
            **payload.model_dump(),
        )
        return PropertyImageResponse.model_validate(inst, from_attributes=True)

    async def update(
        self, image_id: UUID, property_id: UUID, payload: PropertyImageUpdate
    ) -> PropertyImageResponse | None:
        inst = await PropertyImage.get_or_none(id=image_id, property_id=property_id)
        if not inst:
            return None

        updates = payload.model_dump(exclude_none=True)

        if updates.get("is_thumbnail"):
            await PropertyImage.filter(property_id=property_id, is_thumbnail=True).update(
                is_thumbnail=False
            )

        await inst.update_from_dict(updates).save()
        return PropertyImageResponse.model_validate(inst, from_attributes=True)

    async def delete(self, image_id: UUID, property_id: UUID) -> bool:
        return await self.delete_by(id=image_id, property_id=property_id)

    async def list_for_property(self, property_id: UUID) -> list[PropertyImageResponse]:
        images = await PropertyImage.filter(property_id=property_id).order_by("order")
        return [
            PropertyImageResponse.model_validate(img, from_attributes=True)
            for img in images
        ]

    async def reorder(
        self, property_id: UUID, ordered_ids: list[UUID]
    ) -> list[PropertyImageResponse]:
        """Accept an ordered list of image IDs and persist their positions."""
        for position, image_id in enumerate(ordered_ids):
            await PropertyImage.filter(id=image_id, property_id=property_id).update(
                order=position
            )
        return await self.list_for_property(property_id)


class PropertyUnavailabilityCRUD(CRUD[PropertyUnavailability, PropertyUnavailabilityResponse]):  # type: ignore
    async def create_for_property(
        self, property_id: UUID, payload: PropertyUnavailabilityCreate
    ) -> PropertyUnavailabilityResponse:
        inst = await PropertyUnavailability.create(
            property_id=property_id,
            **payload.model_dump(),
        )
        return PropertyUnavailabilityResponse.model_validate(inst, from_attributes=True)

    async def update(
        self,
        unavailability_id: UUID,
        property_id: UUID,
        payload: PropertyUnavailabilityUpdate,
    ) -> PropertyUnavailabilityResponse | None:
        inst = await PropertyUnavailability.get_or_none(
            id=unavailability_id, property_id=property_id
        )
        if not inst:
            return None

        await inst.update_from_dict(payload.model_dump(exclude_none=True)).save()
        return PropertyUnavailabilityResponse.model_validate(inst, from_attributes=True)

    async def delete(self, unavailability_id: UUID, property_id: UUID) -> bool:
        return await self.delete_by(id=unavailability_id, property_id=property_id)

    async def list_for_property(self, property_id: UUID) -> list[PropertyUnavailabilityResponse]:
        items = await PropertyUnavailability.filter(property_id=property_id).order_by(
            "start_datetime"
        )
        return [
            PropertyUnavailabilityResponse.model_validate(item, from_attributes=True)
            for item in items
        ]


class PropertyCRUD(CRUD[Property, PropertyResponse]):  # type: ignore
    async def create_property(self, payload: PropertyCreate, owner_id: UUID) -> PropertyResponse:
        inst = await Property.create(
            owner_id=owner_id,
            **payload.model_dump(),
        )
        await inst.fetch_related("images", "unavailabilities")
        return PropertyResponse.model_validate(inst, from_attributes=True)

    async def update_property(
        self, property_id: UUID, payload: PropertyUpdate, owner_id: UUID
    ) -> PropertyResponse | None:
        inst = await Property.get_or_none(id=property_id, owner_id=owner_id)
        if not inst:
            return None

        await inst.update_from_dict(payload.model_dump(exclude_none=True)).save()
        await inst.fetch_related("images", "unavailabilities")
        return PropertyResponse.model_validate(inst, from_attributes=True)

    async def update_status(
        self, property_id: UUID, payload: PropertyStatusUpdate
    ) -> PropertyResponse | None:
        """Admin-only — no ownership check."""
        inst = await Property.get_or_none(id=property_id)
        if not inst:
            return None

        inst.status = payload.status  # type: ignore
        await inst.save(update_fields=["status"])
        await inst.fetch_related("images", "unavailabilities")
        return PropertyResponse.model_validate(inst, from_attributes=True)

    async def delete_property(self, property_id: UUID, owner_id: UUID) -> bool:
        """Owners can only delete their own properties."""
        return await self.delete_by(id=property_id, owner_id=owner_id)

    async def admin_delete_property(self, property_id: UUID) -> bool:
        return await self.delete_by(id=property_id)

    async def get_property(self, property_id: UUID) -> PropertyResponse | None:
        inst = await Property.get_or_none(id=property_id).prefetch_related(
            "images", "unavailabilities"
        )

        if not inst:
            return None

        return PropertyResponse.model_validate(inst, from_attributes=True)

    async def get_property_for_owner(
        self, property_id: UUID, owner_id: UUID
    ) -> PropertyResponse | None:
        try:
            inst = await Property.get(id=property_id, owner_id=owner_id).prefetch_related(
                "images", "unavailabilities"
            )
        except DoesNotExist:
            return None
        return PropertyResponse.model_validate(inst, from_attributes=True)

    async def get_properties_by_ids(self, ids: list[UUID]) -> list[PropertyListItem]:
        properties = await Property.filter(id__in=ids).prefetch_related("images")
        results: list[PropertyListItem] = []
        for v in properties:
            thumbnail = next(
                (img.url for img in v.images if img.is_thumbnail),  # type: ignore[union-attr]
                None,
            )
            results.append(
                PropertyListItem(
                    id=v.id,
                    name=v.name,
                    city=v.city,
                    sport_types=v.sport_types,
                    status=PropertyStatus(v.status),
                    price_per_hour=v.price_per_hour,
                    currency=v.currency,
                    capacity=v.capacity,
                    is_indoor=v.is_indoor,
                    rating=v.rating,
                    total_reviews=v.total_reviews,
                    thumbnail=thumbnail,
                )
            )
        return results

    async def list_properties(self, filters: PropertyFilters) -> list[PropertyListItem]:
        qs = Property.all()

        if filters.status is not None:
            qs = qs.filter(status=filters.status)
        if filters.city is not None:
            qs = qs.filter(city__icontains=filters.city)
        if filters.sport_type is not None:
            # for SQLite use a raw .filter() override
            target_value = json.dumps(filters.sport_type.value)
            qs = qs.filter(sport_types__contains=target_value)
        if filters.is_indoor is not None:
            qs = qs.filter(is_indoor=filters.is_indoor)
        if filters.has_parking is not None:
            qs = qs.filter(has_parking=filters.has_parking)
        if filters.min_price is not None:
            qs = qs.filter(price_per_hour__gte=filters.min_price)
        if filters.max_price is not None:
            qs = qs.filter(price_per_hour__lte=filters.max_price)
        if filters.min_capacity is not None:
            qs = qs.filter(capacity__gte=filters.min_capacity)
        if filters.owner_id is not None:
            qs = qs.filter(owner_id=filters.owner_id)

        offset = (filters.page - 1) * filters.page_size
        qs = qs.offset(offset).limit(filters.page_size)

        properties = await qs.prefetch_related("images")

        results: list[PropertyListItem] = []
        for v in properties:
            thumbnail = next(
                (img.url for img in v.images if img.is_thumbnail),  # type: ignore[union-attr]
                None,
            )
            results.append(
                PropertyListItem(
                    id=v.id,
                    name=v.name,
                    city=v.city,
                    sport_types=v.sport_types,
                    status=PropertyStatus(v.status),
                    price_per_hour=v.price_per_hour,
                    currency=v.currency,
                    capacity=v.capacity,
                    is_indoor=v.is_indoor,
                    rating=v.rating,
                    total_reviews=v.total_reviews,
                    thumbnail=thumbnail,
                )
            )
        return results


property_crud = PropertyCRUD(Property, PropertyResponse)
property_image_crud = PropertyImageCRUD(PropertyImage, PropertyImageResponse)
property_unavailability_crud = PropertyUnavailabilityCRUD(
    PropertyUnavailability, PropertyUnavailabilityResponse
)


async def assert_owns_property(property_id: UUID, current_user: CurrentUser) -> None:
    """Admins bypass ownership; regular users must own the property."""
    if PropertyScope.ADMIN_WRITE in current_user.scopes:
        return
    property = await property_crud.get_property(property_id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Property not found"
        )
    if property.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to modify this property",
        )
