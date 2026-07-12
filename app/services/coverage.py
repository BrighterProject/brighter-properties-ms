"""Pricing coverage — the day-ranges a property has no price set for.

A day is priced iff its weekday has a ``PropertyWeekdayPrice`` or a
``PropertyDatePriceOverride`` covers it (override wins). Days with neither are
"unpriced" and therefore unbookable.

This is a first-class, queryable concept — distinct from real owner-set
unavailabilities. The frontend date picker uses it to grey out unpriced days;
booking validation instead relies on the price resolver rejecting unpriced
nights (see app.services.price_resolver), so no synthetic unavailability rows
are ever produced.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from app import settings
from app.schemas import UnpricedWindow


def compute_unpriced_windows(
    weekday_rules: list[Any],
    date_overrides: list[Any],
    *,
    start: date,
    end: date,
) -> list[UnpricedWindow]:
    """Return the unpriced day-windows within ``[start, end)`` (end-exclusive).

    Args:
        weekday_rules: The property's ``PropertyWeekdayPrice`` rows.
        date_overrides: The property's ``PropertyDatePriceOverride`` rows.
        start: First day to consider (inclusive).
        end: Day after the last day to consider (exclusive).

    Returns:
        One window per contiguous run of unpriced days; empty when every day is
        priced.
    """
    priced_weekdays = {w.weekday for w in weekday_rules}

    def is_priced(day: date) -> bool:
        if day.weekday() in priced_weekdays:
            return True
        return any(o.start_date <= day <= o.end_date for o in date_overrides)

    windows: list[UnpricedWindow] = []
    gap_start: date | None = None
    day = start
    while day < end:
        if is_priced(day):
            if gap_start is not None:
                windows.append(UnpricedWindow(start_date=gap_start, end_date=day))
                gap_start = None
        elif gap_start is None:
            gap_start = day
        day += timedelta(days=1)
    if gap_start is not None:
        windows.append(UnpricedWindow(start_date=gap_start, end_date=end))
    return windows


async def unpriced_windows(
    property_id: UUID,
    *,
    start: date | None = None,
    end: date | None = None,
    today: date | None = None,
) -> list[UnpricedWindow]:
    """Load the pricing calendar and compute unpriced windows for a property.

    Args:
        property_id: Property to inspect.
        start: First day to consider (defaults to ``today``).
        end: Day after the last day to consider (defaults to
            ``today + BOOKING_WINDOW_DAYS``).
        today: Override for the horizon anchor (defaults to ``date.today()``).

    Returns:
        The unpriced windows within the resolved ``[start, end)`` range.
    """
    from app.models import PropertyDatePriceOverride, PropertyWeekdayPrice

    anchor = today or date.today()
    start = start or anchor
    end = end or (anchor + timedelta(days=settings.booking_window_days))

    weekday_rules = await PropertyWeekdayPrice.filter(property_id=property_id)
    date_overrides = await PropertyDatePriceOverride.filter(
        property_id=property_id,
        start_date__lte=end,
        end_date__gte=start,
    )
    return compute_unpriced_windows(
        weekday_rules, date_overrides, start=start, end=end
    )
