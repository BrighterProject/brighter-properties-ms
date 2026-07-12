"""Per-date pricing endpoints.

Public reads (dates, resolve, coverage) require no auth.
Mutations require properties:schedule scope (owner) or admin:properties:write (admin).
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.crud import assert_owns_property, date_price_crud
from app.deps import CurrentUser, can_schedule_or_admin
from app.limiter import limiter
from app.models import Property
from app.schemas import (
    DatePriceOut,
    DateRangePriceIn,
    PriceResolutionResponse,
    PriceSource,
    PricingCoverageResponse,
    ResolvedNightPrice,
)
from app.services.coverage import unpriced_windows
from app.services.price_resolver import calculate_total, resolve_prices_for_property
from app.services.pricing_cache import sync_pricing_cache

router = APIRouter(prefix="/properties/{property_id}/pricing", tags=["Pricing"])


# ---------------------------------------------------------------------------
# Per-date pricing
# ---------------------------------------------------------------------------


@router.get("/dates", response_model=list[DatePriceOut])
@limiter.limit("120/minute")
async def list_date_prices(
    request: Request,
    property_id: UUID,
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
):
    """Public — the property's priced nights, one row per date.

    Optional ``from_date`` / ``to_date`` restrict the result to that inclusive
    window.
    """
    return await date_price_crud.list_for_property(property_id, from_date, to_date)


@router.put("/dates", response_model=list[DatePriceOut])
@limiter.limit("30/minute")
async def set_date_prices(
    request: Request,
    property_id: UUID,
    payload: DateRangePriceIn,
    current_user: CurrentUser = Depends(can_schedule_or_admin),
):
    """Set every night in ``[start_date, end_date]`` (inclusive) to one price.

    Use ``start_date == end_date`` to price a single day. Existing rows in the
    range are updated; missing ones are created. Returns the affected rows.
    """
    await assert_owns_property(property_id, current_user)
    result = await date_price_crud.upsert_range(property_id, payload)
    await sync_pricing_cache(property_id)
    return result


@router.delete("/dates", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def clear_date_prices(
    request: Request,
    property_id: UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: CurrentUser = Depends(can_schedule_or_admin),
):
    """Clear pricing for every night in ``[start_date, end_date]`` (inclusive).

    The deleted nights become unpriced and therefore unavailable.
    """
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be >= start_date",
        )
    await assert_owns_property(property_id, current_user)
    await date_price_crud.delete_range(property_id, start_date, end_date)
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
    resolved price and source (``date``) per night.

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
