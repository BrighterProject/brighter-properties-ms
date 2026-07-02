"""Derive availability from the pricing calendar.

Business rule (temporary, no schema change): a property is only bookable on days
that have an explicit price. A day has a price if it is covered by a date price
override or its weekday has a weekday price. Days with neither are treated as
unavailable — the base ``price_per_night`` is intentionally ignored here.

Rather than persisting an unavailability row per empty day (unbounded and needing
constant re-sync with the calendar), the empty-day windows are synthesized on the
fly and merged into the existing unavailability channel, so both the booking
overlap check and the frontend date picker block them automatically.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from app import settings
from app.schemas import PropertyUnavailabilityResponse

PRICE_GAP_REASON = "Няма зададена цена за тази дата"


async def price_gap_windows(
    property_id: UUID,
    *,
    horizon_days: int | None = None,
    today: date | None = None,
) -> list[PropertyUnavailabilityResponse]:
    """Synthesize unavailability windows for days that have no price set.

    Args:
        property_id: Property to inspect.
        horizon_days: How far ahead (from ``today``) to synthesize blocks.
        today: Override the start of the horizon (defaults to ``date.today()``).

    Returns:
        A list of unavailability windows (``[start_date, end_date)``, end-exclusive)
        covering each contiguous run of unpriced days within the horizon.
    """
    from app.models import PropertyDatePriceOverride, PropertyWeekdayPrice

    start = today or date.today()
    window = horizon_days if horizon_days is not None else settings.booking_window_days
    end = start + timedelta(days=window)

    priced_weekdays = {
        w.weekday for w in await PropertyWeekdayPrice.filter(property_id=property_id)
    }
    overrides = await PropertyDatePriceOverride.filter(
        property_id=property_id,
        start_date__lte=end,
        end_date__gte=start,
    )

    def is_priced(day: date) -> bool:
        if day.weekday() in priced_weekdays:
            return True
        return any(o.start_date <= day <= o.end_date for o in overrides)

    windows: list[PropertyUnavailabilityResponse] = []
    gap_start: date | None = None
    day = start
    while day < end:
        if is_priced(day):
            if gap_start is not None:
                windows.append(_window(property_id, gap_start, day))
                gap_start = None
        elif gap_start is None:
            gap_start = day
        day += timedelta(days=1)
    if gap_start is not None:
        windows.append(_window(property_id, gap_start, end))

    return windows


def _window(
    property_id: UUID, start: date, end: date
) -> PropertyUnavailabilityResponse:
    """Build a synthetic (non-persisted) unavailability window with a stable id."""
    return PropertyUnavailabilityResponse(
        id=uuid5(NAMESPACE_URL, f"{property_id}:price-gap:{start.isoformat()}"),
        property_id=property_id,
        start_date=start,
        end_date=end,
        reason=PRICE_GAP_REASON,
    )
