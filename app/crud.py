from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from functools import lru_cache
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from loguru import logger
from ms_core import CRUD
from tortoise import Tortoise
from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.expressions import Q
from tortoise.functions import Coalesce
from tortoise.query_utils import Prefetch

from app import settings
from app.deps import CurrentUser
from app.regions import resolve_city_name
from app.scopes import PropertyScope
from app.services.price_resolver import compute_stay_totals

from .models import (
    Property,
    PropertyDatePrice,
    PropertyImage,
    PropertyTranslation,
    PropertyUnavailability,
)
from .schemas import (
    DatePriceOut,
    DateRangePriceIn,
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

_PG_FTS_CONFIG: dict[str, str] = {"en": "english", "ru": "russian", "bg": "bulgarian"}


def _fts_config(locale: str) -> str:
    return _PG_FTS_CONFIG.get(locale, "simple")


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
    except (httpx.RequestError, ValueError) as exc:
        logger.warning("failed to fetch booked property IDs from bookings-ms — {}", exc)
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


# Sentinels push NULL price_from to the end regardless of sort direction (SQLite
# and Postgres order NULLs differently, so we coalesce instead of relying on it).
_NULL_PRICE_HIGH = Decimal("99999999")
_NULL_PRICE_LOW = Decimal("-1")


def _apply_list_order(qs, order_by: str):
    """Apply a stable DB-level ordering to the (no-dates) listing queryset.

    ``recommended`` is left unordered (the historical default / FTS-rank path).
    Price sorts coalesce NULL ``price_from`` to a sentinel so unpriced drafts
    always sort last; ``id`` is the deterministic tie-breaker for pagination.
    """
    if order_by == "price_asc":
        return qs.annotate(
            _sort_price=Coalesce("price_from", _NULL_PRICE_HIGH)
        ).order_by("_sort_price", "id")
    if order_by == "price_desc":
        return qs.annotate(
            _sort_price=Coalesce("price_from", _NULL_PRICE_LOW)
        ).order_by("-_sort_price", "id")
    if order_by == "rating_desc":
        return qs.order_by("-rating", "-total_reviews", "id")
    return qs


async def _order_dated_ids(
    surviving: list[UUID],
    order_by: str,
    avg_by_id: dict[UUID, Decimal],
    rank_map: dict[str, float],
) -> list[UUID]:
    """Order the surviving (fully-priced) ids for a dated search.

    Done Python-side because the effective price is the resolved per-stay average
    (from ``compute_stay_totals``), not a DB column. Python's stable sort keeps
    candidate (DB) order for ties and for the ``recommended`` no-search case.
    """
    if order_by == "price_asc":
        return sorted(surviving, key=lambda pid: avg_by_id[pid])
    if order_by == "price_desc":
        return sorted(surviving, key=lambda pid: avg_by_id[pid], reverse=True)
    if order_by == "rating_desc":
        ratings: dict[UUID, Decimal] = dict(
            await Property.filter(id__in=surviving).values_list("id", "rating")
        )
        return sorted(
            surviving, key=lambda pid: ratings.get(pid) or Decimal(0), reverse=True
        )
    if rank_map:  # recommended with an FTS search term
        return sorted(
            surviving, key=lambda pid: rank_map.get(str(pid), 0.0), reverse=True
        )
    return surviving


def _resolve_detail_city(
    resp: PropertyResponse, settlement_ekatte: str | None, locale: str
) -> PropertyResponse:
    """Return ``resp`` with ``city`` resolved from the settlement.

    Mirrors ``_build_list_item``: the settlement name in the requested locale
    wins, falling back to the legacy free-text ``city`` when the settlement is
    absent or unknown. Returns a copy — the input is left untouched.
    """
    return resp.model_copy(
        update={"city": resolve_city_name(settlement_ekatte, locale) or resp.city}
    )


def _build_list_item(
    v,
    locale: str,
    *,
    stay_total: Decimal | None = None,
    stay_nights: int | None = None,
) -> PropertyListItem:
    """Project a prefetched Property row into a ``PropertyListItem``.

    Requires ``images`` and ``translations`` to be prefetched on ``v``.
    """
    thumbnail = next(
        (img.url for img in v.images if img.is_thumbnail),  # type: ignore[union-attr]
        None,
    )
    tr = _resolve_translation(v.translations, locale)  # type: ignore[union-attr]
    return PropertyListItem(
        id=v.id,
        name=tr.name if tr else FALLBACK_NAME,
        description=tr.description if tr else "",
        region_code=v.region_code,
        settlement_ekatte=v.settlement_ekatte,
        city=resolve_city_name(v.settlement_ekatte, locale) or v.city,
        latitude=v.latitude,
        longitude=v.longitude,
        property_type=v.property_type,
        status=PropertyStatus(v.status),
        price_from=v.price_from,
        currency=v.currency,
        max_guests=v.max_guests,
        bedrooms=v.bedrooms,
        rooms=v.rooms,
        rating=v.rating,
        total_reviews=v.total_reviews,
        thumbnail=thumbnail,
        cancellation_policy=v.cancellation_policy,
        stay_total=stay_total,
        stay_nights=stay_nights,
    )


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
        except IntegrityError as err:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Translation for locale '{payload.locale}' already exists",
            ) from err
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

PREFETCH = (
    "images",
    "unavailabilities",
    "translations",
    "date_prices",
)


class PropertyCRUD(CRUD[Property, PropertyResponse]):  # type: ignore
    async def create_property(
        self, payload: PropertyCreate, owner_id: UUID
    ) -> PropertyResponse:
        property_data = payload.model_dump(exclude={"translations", "images"})
        inst = await Property.create(owner_id=owner_id, **property_data)
        await inst.fetch_related(*PREFETCH)
        return PropertyResponse.model_validate(inst, from_attributes=True)

    async def update_property(
        self, property_id: UUID, payload: PropertyUpdate, owner_id: UUID | None = None
    ) -> PropertyResponse | None:
        filters: dict = {"id": property_id}
        if owner_id:
            filters["owner_id"] = owner_id
        inst = await Property.get_or_none(**filters)
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

    async def count_by_owner(self, owner_id: UUID) -> int:
        return await Property.filter(owner_id=owner_id).count()

    async def get_property(
        self, property_id: UUID, locale: str = settings.DEFAULT_LOCALE
    ) -> PropertyResponse | None:
        inst = await Property.get_or_none(id=property_id).prefetch_related(*PREFETCH)

        if not inst:
            return None

        return _resolve_detail_city(
            PropertyResponse.model_validate(inst, from_attributes=True),
            inst.settlement_ekatte,
            locale,
        )

    async def get_property_for_owner(
        self,
        property_id: UUID,
        owner_id: UUID,
        locale: str = settings.DEFAULT_LOCALE,
    ) -> PropertyResponse | None:
        try:
            inst = await Property.get(
                id=property_id, owner_id=owner_id
            ).prefetch_related(*PREFETCH)
        except DoesNotExist:
            return None
        return _resolve_detail_city(
            PropertyResponse.model_validate(inst, from_attributes=True),
            inst.settlement_ekatte,
            locale,
        )

    async def get_properties_by_ids(
        self, ids: list[UUID], locale: str = settings.DEFAULT_LOCALE
    ) -> list[PropertyListItem]:
        properties = await Property.filter(id__in=ids).prefetch_related(
            "images", "translations"
        )
        return [_build_list_item(v, locale) for v in properties]

    async def list_properties(
        self,
        filters: PropertyFilters,
        locale: str = settings.DEFAULT_LOCALE,
        admin_view: bool = False,
    ) -> tuple[list[PropertyListItem], int]:
        """Return ``(page_items, total)`` where ``total`` is the pre-pagination
        match count (surfaced as ``X-Total-Count`` by the router)."""
        qs = Property.all()
        rank_map: dict[str, float] = {}
        has_dates = (
            filters.available_from is not None and filters.available_to is not None
        )

        if filters.status is not None:
            qs = qs.filter(status=filters.status)
        if filters.region_code is not None:
            qs = qs.filter(region_code=filters.region_code)
        if filters.settlement_ekatte is not None:
            qs = qs.filter(settlement_ekatte=filters.settlement_ekatte)
        if filters.city is not None:
            qs = qs.filter(city__icontains=filters.city)
        if filters.q is not None:
            term = filters.q.strip()
            if term:
                if settings.db_url.startswith("sqlite"):
                    qs = qs.filter(
                        Q(translations__name__icontains=term)
                        | Q(translations__description__icontains=term)
                        | Q(translations__address__icontains=term)
                    ).distinct()
                else:
                    pg_cfg = _fts_config(locale)
                    conn = Tortoise.get_connection("default")
                    rows = await conn.execute_query_dict(
                        """
                        SELECT property_id::text AS pid,
                               MAX(TS_RANK(search_vector,
                                   WEBSEARCH_TO_TSQUERY($1::regconfig, $2))) AS rank
                        FROM property_translations
                        WHERE search_vector @@ WEBSEARCH_TO_TSQUERY($1::regconfig, $2)
                          AND locale = $3
                        GROUP BY property_id
                        ORDER BY rank DESC
                        """,
                        [pg_cfg, term, locale],
                    )
                    if not rows:
                        return [], 0
                    rank_map = {r["pid"]: float(r["rank"]) for r in rows}
                    qs = qs.filter(id__in=list(rank_map.keys()))
        if filters.property_type is not None:
            qs = qs.filter(property_type__in=filters.property_type)
        if filters.has_parking is not None:
            qs = qs.filter(has_parking=filters.has_parking)
        if filters.free_cancellation:
            qs = qs.filter(cancellation_policy="free")
        if filters.amenities:
            for amenity in filters.amenities:
                qs = qs.filter(amenities__contains=f'"{amenity}"')
        # Without a date range, the price filter operates on ``price_from`` (the
        # "from X" cheapest night). With dates it operates on the resolved stay
        # rate and is applied in ``_list_with_dates`` after pricing the calendar.
        if not has_dates:
            if filters.min_price is not None:
                qs = qs.filter(price_from__gte=filters.min_price)
            if filters.max_price is not None:
                qs = qs.filter(price_from__lte=filters.max_price)
        if filters.min_rating is not None:
            qs = qs.filter(rating__gte=filters.min_rating)
        if filters.min_guests is not None:
            qs = qs.filter(max_guests__gte=filters.min_guests)
        if filters.bedrooms is not None:
            qs = qs.filter(bedrooms__gte=filters.bedrooms)
        if filters.owner_id is not None:
            # Owner-scoped listing (admin panel) shows the owner's own drafts,
            # including ones without pricing yet.
            qs = qs.filter(owner_id=filters.owner_id)
        elif not admin_view:
            # Public browse: hide properties with no bookable (priced) days.
            qs = qs.filter(has_valid_pricing=True)
        # admin_view with no owner_id: authenticated admin sees every property
        # regardless of status or pricing — no filter applied.

        if has_dates:
            return await self._list_with_dates(qs, filters, locale, rank_map)
        return await self._list_without_dates(qs, filters, locale, rank_map)

    async def _list_without_dates(
        self,
        qs,
        filters: PropertyFilters,
        locale: str,
        rank_map: dict[str, float],
    ) -> tuple[list[PropertyListItem], int]:
        """No date range: sort and paginate at the DB level, count once."""
        total = await qs.count()
        qs = _apply_list_order(qs, filters.order_by)
        offset = (filters.page - 1) * filters.page_size
        qs = qs.offset(offset).limit(filters.page_size)

        properties = await qs.prefetch_related(
            "images",
            Prefetch(
                "translations",
                queryset=PropertyTranslation.all().only(
                    "id", "property_id", "locale", "name", "description", "address"
                ),
            ),
        )
        results = [_build_list_item(v, locale) for v in properties]
        # ``recommended`` preserves the historical FTS-rank ordering of the page.
        if filters.order_by == "recommended" and rank_map:
            results.sort(key=lambda p: rank_map.get(str(p.id), 0.0), reverse=True)
        return results, total

    async def _list_with_dates(
        self,
        qs,
        filters: PropertyFilters,
        locale: str,
        rank_map: dict[str, float],
    ) -> tuple[list[PropertyListItem], int]:
        """Date range: exclude unavailable stays, price the calendar, then filter
        and sort on the resolved per-stay rate before paginating."""
        af = filters.available_from
        at = filters.available_to
        assert af is not None and at is not None  # guaranteed by caller

        # Overlap: unavail.start < checkOut AND unavail.end > checkIn
        unavailable_ids = await PropertyUnavailability.filter(
            start_date__lt=at,
            end_date__gt=af,
        ).values_list("property_id", flat=True)
        booked_ids = await _get_booked_property_ids(af, at)
        excluded = set(map(str, unavailable_ids)) | {str(bid) for bid in booked_ids}
        if excluded:
            qs = qs.exclude(id__in=list(excluded))

        nights = (at - af).days
        qs = qs.filter(min_nights__lte=nights, max_nights__gte=nights)

        # A stay is only bookable if every night is priced; ``compute_stay_totals``
        # omits any property with an unpriced night in the range, so partially
        # priced properties are never resurrected by the price filter below.
        candidate_ids = list(await qs.values_list("id", flat=True))
        stay_totals = await compute_stay_totals(candidate_ids, af, at)

        # Filter on the resolved average nightly rate, preserving candidate order.
        avg_by_id: dict[UUID, Decimal] = {}
        surviving: list[UUID] = []
        for pid in candidate_ids:
            stay_sum = stay_totals.get(pid)
            if stay_sum is None:
                continue
            avg = stay_sum / nights
            if filters.min_price is not None and avg < filters.min_price:
                continue
            if filters.max_price is not None and avg > filters.max_price:
                continue
            avg_by_id[pid] = avg
            surviving.append(pid)

        ordered = await _order_dated_ids(
            surviving, filters.order_by, avg_by_id, rank_map
        )
        total = len(ordered)
        offset = (filters.page - 1) * filters.page_size
        page_ids = ordered[offset : offset + filters.page_size]
        if not page_ids:
            return [], total

        props = await Property.filter(id__in=page_ids).prefetch_related(
            "images",
            Prefetch(
                "translations",
                queryset=PropertyTranslation.all().only(
                    "id", "property_id", "locale", "name", "description", "address"
                ),
            ),
        )
        by_id = {p.id: p for p in props}
        results = [
            _build_list_item(
                by_id[pid], locale, stay_total=stay_totals[pid], stay_nights=nights
            )
            for pid in page_ids
            if pid in by_id
        ]
        return results, total


property_crud = PropertyCRUD(Property, PropertyResponse)
property_image_crud = PropertyImageCRUD(PropertyImage, PropertyImageResponse)
property_unavailability_crud = PropertyUnavailabilityCRUD(
    PropertyUnavailability, PropertyUnavailabilityResponse
)
property_translation_crud = PropertyTranslationCRUD(
    PropertyTranslation, TranslationResponse
)


# ---------------------------------------------------------------------------
# Per-date pricing CRUD
# ---------------------------------------------------------------------------


class DatePriceCRUD(CRUD[PropertyDatePrice, DatePriceOut]):  # type: ignore
    async def list_for_property(
        self,
        property_id: UUID,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[DatePriceOut]:
        """List a property's priced nights, optionally within ``[from_date, to_date]``."""
        qs = PropertyDatePrice.filter(property_id=property_id)
        if from_date:
            qs = qs.filter(date__gte=from_date)
        if to_date:
            qs = qs.filter(date__lte=to_date)
        items = await qs.order_by("date")
        return [DatePriceOut.model_validate(i, from_attributes=True) for i in items]

    async def upsert_range(
        self, property_id: UUID, payload: DateRangePriceIn
    ) -> list[DatePriceOut]:
        """Set every night in ``[start_date, end_date]`` (inclusive) to ``price``.

        Existing rows in the range are updated; missing ones are created — one
        row per night. Returns the resulting rows ordered by date.
        """
        days = [
            payload.start_date + timedelta(days=i)
            for i in range((payload.end_date - payload.start_date).days + 1)
        ]
        existing = {
            row.date: row
            for row in await PropertyDatePrice.filter(
                property_id=property_id,
                date__gte=payload.start_date,
                date__lte=payload.end_date,
            )
        }

        to_update: list[PropertyDatePrice] = []
        to_create: list[PropertyDatePrice] = []
        for day in days:
            row = existing.get(day)
            if row is not None:
                if row.price != payload.price:
                    row.price = payload.price
                    to_update.append(row)
            else:
                to_create.append(
                    PropertyDatePrice(
                        property_id=property_id, date=day, price=payload.price
                    )
                )

        if to_update:
            await PropertyDatePrice.bulk_update(to_update, fields=["price"])
        if to_create:
            await PropertyDatePrice.bulk_create(to_create)

        return await self.list_for_property(
            property_id, payload.start_date, payload.end_date
        )

    async def delete_range(
        self, property_id: UUID, start_date: date, end_date: date
    ) -> int:
        """Delete every priced night in ``[start_date, end_date]`` (inclusive).

        Those dates become unpriced and therefore unavailable. Returns the number
        of rows removed.
        """
        return await PropertyDatePrice.filter(
            property_id=property_id,
            date__gte=start_date,
            date__lte=end_date,
        ).delete()


date_price_crud = DatePriceCRUD(PropertyDatePrice, DatePriceOut)


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
