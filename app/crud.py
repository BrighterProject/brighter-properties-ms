from __future__ import annotations

from datetime import date
from functools import lru_cache
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from ms_core import CRUD
from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.expressions import Q

from app import settings
from app.deps import CurrentUser
from app.scopes import PropertyScope

from .models import Property, PropertyImage, PropertyTranslation, PropertyUnavailability
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
    TranslationCreate,
    TranslationResponse,
    TranslationUpdate,
)

FALLBACK_NAME = "Untitled"


@lru_cache(maxsize=1)
def _bookings_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.bookings_ms_url,
        timeout=httpx.Timeout(3.0),
        follow_redirects=True,
    )


async def _get_booked_property_ids(from_date: date, to_date: date) -> list[UUID]:
    """Return property IDs with active bookings overlapping [from_date, to_date).
    Fails silently (returns empty list) if bookings-ms is unreachable."""
    try:
        resp = await _bookings_http_client().get(
            "/bookings/occupied-property-ids",
            params={"from_date": str(from_date), "to_date": str(to_date)},
        )
        if resp.status_code == 200:
            return [UUID(pid) for pid in resp.json()]
    except (httpx.RequestError, ValueError):
        pass
    return []


def _resolve_translation(translations, locale: str):
    """Return best-match translation for locale, falling back to bg then first."""
    by_locale = {t.locale: t for t in translations}
    return (
        by_locale.get(locale)
        or by_locale.get(settings.DEFAULT_LOCALE)
        or (next(iter(by_locale.values())) if by_locale else None)
    )


def _resolve_name(translations, locale: str) -> str:
    tr = _resolve_translation(translations, locale)
    return tr.name if tr else FALLBACK_NAME


# ---------------------------------------------------------------------------
# Images CRUD (unchanged)
# ---------------------------------------------------------------------------


class PropertyImageCRUD(CRUD[PropertyImage, PropertyImageResponse]):  # type: ignore
    async def create_for_property(
        self, property_id: UUID, payload: PropertyImageCreate
    ) -> PropertyImageResponse:
        if payload.is_thumbnail:
            await PropertyImage.filter(
                property_id=property_id, is_thumbnail=True
            ).update(is_thumbnail=False)

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
            await PropertyImage.filter(
                property_id=property_id, is_thumbnail=True
            ).update(is_thumbnail=False)

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

    async def replace_for_property(
        self, property_id: UUID, images: list[PropertyImageCreate]
    ) -> None:
        await PropertyImage.filter(property_id=property_id).delete()
        for img in images:
            await PropertyImage.create(property_id=property_id, **img.model_dump())

    async def reorder(
        self, property_id: UUID, ordered_ids: list[UUID]
    ) -> list[PropertyImageResponse]:
        for position, image_id in enumerate(ordered_ids):
            await PropertyImage.filter(id=image_id, property_id=property_id).update(
                order=position
            )
        return await self.list_for_property(property_id)


# ---------------------------------------------------------------------------
# Unavailabilities CRUD (unchanged)
# ---------------------------------------------------------------------------


class PropertyUnavailabilityCRUD(
    CRUD[PropertyUnavailability, PropertyUnavailabilityResponse]
):  # type: ignore
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

    async def list_for_property(
        self, property_id: UUID
    ) -> list[PropertyUnavailabilityResponse]:
        items = await PropertyUnavailability.filter(property_id=property_id).order_by(
            "start_date"
        )
        return [
            PropertyUnavailabilityResponse.model_validate(item, from_attributes=True)
            for item in items
        ]


# ---------------------------------------------------------------------------
# Translations CRUD
# ---------------------------------------------------------------------------


class PropertyTranslationCRUD(CRUD[PropertyTranslation, TranslationResponse]):  # type: ignore
    async def create_for_property(
        self, property_id: UUID, payload: TranslationCreate
    ) -> TranslationResponse:
        try:
            inst = await PropertyTranslation.create(
                property_id=property_id,
                **payload.model_dump(),
            )
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Translation for locale '{payload.locale}' already exists",
            )
        return TranslationResponse.model_validate(inst, from_attributes=True)

    async def update(
        self,
        property_id: UUID,
        locale: str,
        payload: TranslationUpdate,
    ) -> TranslationResponse | None:
        inst = await PropertyTranslation.get_or_none(
            property_id=property_id, locale=locale
        )
        if not inst:
            return None

        await inst.update_from_dict(payload.model_dump(exclude_none=True)).save()
        return TranslationResponse.model_validate(inst, from_attributes=True)

    async def delete(self, property_id: UUID, locale: str) -> bool:
        count = await PropertyTranslation.filter(
            property_id=property_id, locale=locale
        ).delete()
        return count > 0

    async def upsert_for_property(
        self, property_id: UUID, translations: dict[str, TranslationUpdate]
    ) -> None:
        for locale, tr in translations.items():
            tr_dict = tr.model_dump(exclude_none=True)
            existing = await PropertyTranslation.get_or_none(
                property_id=property_id, locale=locale
            )
            if existing:
                if tr_dict:
                    await existing.update_from_dict(tr_dict).save()
            else:
                if {"name", "description", "address"}.issubset(tr_dict):
                    await PropertyTranslation.create(
                        property_id=property_id, locale=locale, **tr_dict
                    )

    async def list_for_property(self, property_id: UUID) -> list[TranslationResponse]:
        items = await PropertyTranslation.filter(property_id=property_id).order_by(
            "locale"
        )
        return [
            TranslationResponse.model_validate(item, from_attributes=True)
            for item in items
        ]


# ---------------------------------------------------------------------------
# Property CRUD
# ---------------------------------------------------------------------------

PREFETCH = ("images", "unavailabilities", "translations")


class PropertyCRUD(CRUD[Property, PropertyResponse]):  # type: ignore
    async def create_property(
        self, payload: PropertyCreate, owner_id: UUID
    ) -> PropertyResponse:
        translations_data = payload.translations
        images_data = payload.images
        property_data = payload.model_dump(exclude={"translations", "images"})

        inst = await Property.create(owner_id=owner_id, **property_data)

        for tr in translations_data:
            await PropertyTranslation.create(property_id=inst.id, **tr.model_dump())

        for img in images_data:
            await PropertyImage.create(property_id=inst.id, **img.model_dump())

        await inst.fetch_related(*PREFETCH)
        return PropertyResponse.model_validate(inst, from_attributes=True)

    async def update_property(
        self, property_id: UUID, payload: PropertyUpdate, owner_id: UUID
    ) -> PropertyResponse | None:
        inst = await Property.get_or_none(id=property_id, owner_id=owner_id)
        if not inst:
            return None

        property_fields = payload.model_dump(
            exclude_none=True, exclude={"translations", "images"}
        )
        if property_fields:
            await inst.update_from_dict(property_fields).save()

        await inst.fetch_related(*PREFETCH)
        return PropertyResponse.model_validate(inst, from_attributes=True)

    async def update_status(
        self, property_id: UUID, payload: PropertyStatusUpdate
    ) -> PropertyResponse | None:
        inst = await Property.get_or_none(id=property_id)
        if not inst:
            return None

        inst.status = payload.status  # type: ignore
        await inst.save(update_fields=["status"])
        await inst.fetch_related(*PREFETCH)
        return PropertyResponse.model_validate(inst, from_attributes=True)

    async def delete_property(self, property_id: UUID, owner_id: UUID) -> bool:
        return await self.delete_by(id=property_id, owner_id=owner_id)

    async def admin_delete_property(self, property_id: UUID) -> bool:
        return await self.delete_by(id=property_id)

    async def get_property(self, property_id: UUID) -> PropertyResponse | None:
        inst = await Property.get_or_none(id=property_id).prefetch_related(*PREFETCH)

        if not inst:
            return None

        return PropertyResponse.model_validate(inst, from_attributes=True)

    async def get_property_for_owner(
        self, property_id: UUID, owner_id: UUID
    ) -> PropertyResponse | None:
        try:
            inst = await Property.get(
                id=property_id, owner_id=owner_id
            ).prefetch_related(*PREFETCH)
        except DoesNotExist:
            return None
        return PropertyResponse.model_validate(inst, from_attributes=True)

    async def get_properties_by_ids(
        self, ids: list[UUID], locale: str = settings.DEFAULT_LOCALE
    ) -> list[PropertyListItem]:
        properties = await Property.filter(id__in=ids).prefetch_related(
            "images", "translations"
        )
        results: list[PropertyListItem] = []
        for v in properties:
            thumbnail = next(
                (img.url for img in v.images if img.is_thumbnail),  # type: ignore[union-attr]
                None,
            )
            tr = _resolve_translation(v.translations, locale)  # type: ignore[union-attr]
            results.append(
                PropertyListItem(
                    id=v.id,
                    name=tr.name if tr else FALLBACK_NAME,
                    description=tr.description if tr else "",
                    city=v.city,
                    property_type=v.property_type,
                    status=PropertyStatus(v.status),
                    price_per_night=v.price_per_night,
                    currency=v.currency,
                    max_guests=v.max_guests,
                    bedrooms=v.bedrooms,
                    rooms=v.rooms,
                    rating=v.rating,
                    total_reviews=v.total_reviews,
                    thumbnail=thumbnail,
                )
            )
        return results

    async def list_properties(
        self, filters: PropertyFilters, locale: str = settings.DEFAULT_LOCALE
    ) -> list[PropertyListItem]:
        qs = Property.all()

        if filters.status is not None:
            qs = qs.filter(status=filters.status)
        if filters.city is not None:
            qs = qs.filter(city__icontains=filters.city)
        if filters.property_type is not None:
            qs = qs.filter(property_type__in=filters.property_type)
        if filters.has_parking is not None:
            qs = qs.filter(has_parking=filters.has_parking)
        if filters.free_cancellation:
            qs = qs.filter(cancellation_policy="free")
        if filters.amenities:
            for amenity in filters.amenities:
                qs = qs.filter(amenities__contains=f'"{amenity}"')
        if filters.min_price is not None:
            qs = qs.filter(price_per_night__gte=filters.min_price)
        if filters.max_price is not None:
            qs = qs.filter(price_per_night__lte=filters.max_price)
        if filters.min_rating is not None:
            qs = qs.filter(rating__gte=filters.min_rating)
        if filters.min_guests is not None:
            qs = qs.filter(max_guests__gte=filters.min_guests)
        if filters.bedrooms is not None:
            qs = qs.filter(bedrooms__gte=filters.bedrooms)
        if filters.owner_id is not None:
            qs = qs.filter(owner_id=filters.owner_id)

        if filters.available_from is not None and filters.available_to is not None:
            af = filters.available_from
            at = filters.available_to
            # Overlap: unavail.start < checkOut AND unavail.end > checkIn
            unavailable_ids = await PropertyUnavailability.filter(
                start_date__lt=at,
                end_date__gt=af,
            ).values_list("property_id", flat=True)
            booked_ids = await _get_booked_property_ids(af, at)
            excluded = set(map(str, unavailable_ids)) | {str(bid) for bid in booked_ids}
            if excluded:
                qs = qs.exclude(id__in=list(excluded))

            requested_nights = (at - af).days
            qs = qs.filter(min_nights__lte=requested_nights)
            qs = qs.filter(Q(max_nights__gte=requested_nights))

        offset = (filters.page - 1) * filters.page_size
        qs = qs.offset(offset).limit(filters.page_size)

        properties = await qs.prefetch_related("images", "translations")

        results: list[PropertyListItem] = []
        for v in properties:
            thumbnail = next(
                (img.url for img in v.images if img.is_thumbnail),  # type: ignore[union-attr]
                None,
            )
            tr = _resolve_translation(v.translations, locale)  # type: ignore[union-attr]
            results.append(
                PropertyListItem(
                    id=v.id,
                    name=tr.name if tr else FALLBACK_NAME,
                    description=tr.description if tr else "",
                    city=v.city,
                    property_type=v.property_type,
                    status=PropertyStatus(v.status),
                    price_per_night=v.price_per_night,
                    currency=v.currency,
                    max_guests=v.max_guests,
                    bedrooms=v.bedrooms,
                    rooms=v.rooms,
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
property_translation_crud = PropertyTranslationCRUD(
    PropertyTranslation, TranslationResponse
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
