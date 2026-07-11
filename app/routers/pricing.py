"""Pseudo-dynamic pricing endpoints.

Public reads (weekdays, overrides, resolve) require no auth.
Mutations require properties:schedule scope (owner) or admin:properties:write (admin).
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.crud import assert_owns_property, date_override_crud, weekday_price_crud
from app.deps import CurrentUser, can_schedule_or_admin
from app.limiter import limiter
from app.models import Property
from app.schemas import (
    DatePriceOverrideIn,
    DatePriceOverrideOut,
    DatePriceOverrideUpdate,
    PriceResolutionResponse,
    PriceSource,
    PricingCoverageResponse,
    ResolvedNightPrice,
    WeekdayPriceIn,
    WeekdayPriceOut,
)
from app.services.coverage import unpriced_windows
from app.services.price_resolver import calculate_total, resolve_prices_for_property
from app.services.pricing_cache import sync_pricing_cache

router = APIRouter(prefix="/properties/{property_id}/pricing", tags=["Pricing"])


# ---------------------------------------------------------------------------
# Weekday pricing
# ---------------------------------------------------------------------------


@router.get("/weekdays", response_model=list[WeekdayPriceOut])
@limiter.limit("120/minute")
async def list_weekday_prices(request: Request, property_id: UUID):
    """Public — returns owner-set weekday price overrides."""
    return await weekday_price_crud.list_for_property(property_id)


@router.put("/weekdays", response_model=list[WeekdayPriceOut])
@limiter.limit("30/minute")
async def upsert_weekday_prices(
    request: Request,
    property_id: UUID,
    rules: list[WeekdayPriceIn],
    current_user: CurrentUser = Depends(can_schedule_or_admin),
):
    """Replaces all weekday price rules for the property atomically.

    Sending an empty list clears all weekday overrides.
    Each weekday (0–6) must appear at most once.
    """
    weekdays = [r.weekday for r in rules]
    if len(weekdays) != len(set(weekdays)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Duplicate weekdays in request",
        )
    await assert_owns_property(property_id, current_user)
    result = await weekday_price_crud.upsert_all(property_id, rules)
    await sync_pricing_cache(property_id)
    return result


# ---------------------------------------------------------------------------
# Date price overrides
# ---------------------------------------------------------------------------


@router.get("/overrides", response_model=list[DatePriceOverrideOut])
@limiter.limit("120/minute")
async def list_overrides(
    request: Request,
    property_id: UUID,
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
):
    """Public — returns holiday/special-date price overrides.

    Optional ``from_date`` / ``to_date`` filter returns overrides that
    overlap the given window.
    """
    return await date_override_crud.list_for_property(property_id, from_date, to_date)


@router.post(
    "/overrides",
    response_model=DatePriceOverrideOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("30/minute")
async def create_override(
    request: Request,
    property_id: UUID,
    payload: DatePriceOverrideIn,
    current_user: CurrentUser = Depends(can_schedule_or_admin),
):
    await assert_owns_property(property_id, current_user)
    result = await date_override_crud.create_for_property(property_id, payload)
    await sync_pricing_cache(property_id)
    return result


@router.patch("/overrides/{override_id}", response_model=DatePriceOverrideOut)
@limiter.limit("30/minute")
async def update_override(
    request: Request,
    property_id: UUID,
    override_id: UUID,
    payload: DatePriceOverrideUpdate,
    current_user: CurrentUser = Depends(can_schedule_or_admin),
):
    await assert_owns_property(property_id, current_user)
    item = await date_override_crud.update(override_id, property_id, payload)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Override not found"
        )
    await sync_pricing_cache(property_id)
    return item


@router.delete("/overrides/{override_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def delete_override(
    request: Request,
    property_id: UUID,
    override_id: UUID,
    current_user: CurrentUser = Depends(can_schedule_or_admin),
):
    await assert_owns_property(property_id, current_user)
    deleted = await date_override_crud.delete(override_id, property_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Override not found"
        )
    await sync_pricing_cache(property_id)


# ---------------------------------------------------------------------------
# Price resolution
# ---------------------------------------------------------------------------


@router.get("/resolve", response_model=PriceResolutionResponse)
@limiter.limit("120/minute")
async def resolve_pricing(
    request: Request,
    property_id: UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
):
    """Public — returns per-night price breakdown for a date range.

    ``start_date`` is the check-in date; ``end_date`` is the checkout date
    (excluded from the nightly results).  ``end_date`` must be after ``start_date``.

    Response includes ``currency``, ``total``, and a ``nights`` list with the
    resolved price and source (``weekday`` | ``date_override``) per night.

    Returns **409** with the list of unpriced dates when any night in the range
    has no price configured — such a stay is not bookable.
    """
    if end_date <= start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be after start_date",
        )

    prop = await Property.get_or_none(id=property_id)
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Property not found"
        )

    nights = await resolve_prices_for_property(
        property_id=property_id,
        start_date=start_date,
        end_date=end_date,
    )

    unpriced = [n.date for n in nights if n.source == PriceSource.UNPRICED]
    if unpriced:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Some nights in the requested range have no price set.",
                "unpriced_dates": [d.isoformat() for d in unpriced],
            },
        )

    return PriceResolutionResponse(
        currency=prop.currency,
        nights=[
            ResolvedNightPrice(
                date=n.date,
                price=n.price,
                source=PriceSource(n.source),
                label=n.label,
            )
            for n in nights
        ],
        total=calculate_total(nights),
    )


@router.get("/coverage", response_model=PricingCoverageResponse)
@limiter.limit("120/minute")
async def pricing_coverage(
    request: Request,
    property_id: UUID,
    start: date = Query(...),
    end: date = Query(...),
):
    """Public — day-windows within ``[start, end)`` that have no price set.

    Used by the frontend date picker to disable unbookable days. Booking
    validation does not call this — it relies on the resolver's 409.
    """
    if end <= start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end must be after start",
        )
    windows = await unpriced_windows(property_id, start=start, end=end)
    return PricingCoverageResponse(unpriced_windows=windows)
