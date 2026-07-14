"""Pricing coverage — the day-ranges a property has no price set for.

A day is priced iff it has a ``PropertyDatePrice`` row. Days without one are
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
    date_prices: list[Any],
    *,
    start: date,
    end: date,
) -> list[UnpricedWindow]:
    """Return the unpriced day-windows within ``[start, end)`` (end-exclusive).

    Args:
        date_prices: The property's ``PropertyDatePrice`` rows.
        start: First day to consider (inclusive).
        end: Day after the last day to consider (exclusive).

    Returns:
        One window per contiguous run of unpriced days; empty when every day is
        priced.
    """
    priced_days = {p.date for p in date_prices}

    windows: list[UnpricedWindow] = []
    gap_start: date | None = None
    day = start
    while day < end:
        if day in priced_days:
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
    from app.models import PropertyDatePrice

    anchor = today or date.today()
    start = start or anchor
    end = end or (anchor + timedelta(days=settings.booking_window_days))

    date_prices = await PropertyDatePrice.filter(
        property_id=property_id,
        date__gte=start,
        date__lt=end,
    )
    return compute_unpriced_windows(date_prices, start=start, end=end)
