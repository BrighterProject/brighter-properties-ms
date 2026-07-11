"""Maintain a property's denormalized pricing cache.

Two system-owned fields on ``Property`` are kept in sync with the pricing
calendar (``PropertyWeekdayPrice`` + ``PropertyDatePriceOverride``); neither is
ever owner input:

* ``price_from`` — the cheapest configured nightly rate (the "from X / night"
  price shown on cards). ``None`` when the property has no pricing at all.
* ``has_valid_pricing`` — whether at least one day within the rolling booking
  horizon (``BOOKING_WINDOW_DAYS`` from today) is priced. Drives whether the
  property is publicly listable. Weekday rules recur weekly, so any property with
  ``>=1`` weekday price is always valid; an override-only property is valid only
  while an override intersects the horizon.

Recomputed on every pricing-calendar write and by
``scripts/recompute_pricing_cache.py`` (nightly) to catch horizon drift as time
passes.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from app import settings


def compute_price_from(
    weekday_rules: list[Any], date_overrides: list[Any]
) -> Decimal | None:
    """Return the cheapest configured nightly price, or ``None`` if none is set.

    Args:
        weekday_rules: The property's ``PropertyWeekdayPrice`` rows.
        date_overrides: The property's ``PropertyDatePriceOverride`` rows.

    Returns:
        The minimum configured price across both sources, or ``None`` when the
        property has no pricing at all.
    """
    prices: list[Decimal] = [w.price for w in weekday_rules]
    prices += [o.price for o in date_overrides]
    return min(prices) if prices else None


def has_valid_pricing(
    weekday_rules: list[Any],
    date_overrides: list[Any],
    *,
    today: date,
    horizon_days: int,
) -> bool:
    """Return whether any day in ``[today, today + horizon_days)`` is priced.

    A weekday rule recurs weekly and therefore always covers a day in any
    non-empty horizon. An override contributes only while it intersects the
    horizon.

    Args:
        weekday_rules: The property's ``PropertyWeekdayPrice`` rows.
        date_overrides: The property's ``PropertyDatePriceOverride`` rows.
        today: First day of the rolling horizon (inclusive).
        horizon_days: Length of the horizon in days.

    Returns:
        ``True`` if at least one priced day falls within the horizon.
    """
    if horizon_days <= 0:
        return False
    if weekday_rules:
        return True
    end = today + timedelta(days=horizon_days)  # exclusive
    return any(o.start_date < end and o.end_date >= today for o in date_overrides)


async def sync_pricing_cache(property_id: UUID, *, today: date | None = None) -> None:
    """Recompute and persist ``price_from`` and ``has_valid_pricing``.

    Fetches the property's pricing calendar once and writes both cache fields,
    saving only when a value actually changed.

    Args:
        property_id: Property whose cache to refresh.
        today: Override the start of the horizon (defaults to ``date.today()``).
    """
    from app.models import Property, PropertyDatePriceOverride, PropertyWeekdayPrice

    prop = await Property.get_or_none(id=property_id)
    if prop is None:
        return

    weekday_rules = await PropertyWeekdayPrice.filter(property_id=property_id)
    date_overrides = await PropertyDatePriceOverride.filter(property_id=property_id)

    price_from = compute_price_from(weekday_rules, date_overrides)
    valid = has_valid_pricing(
        weekday_rules,
        date_overrides,
        today=today or date.today(),
        horizon_days=settings.booking_window_days,
    )

    changed_fields: list[str] = []
    if prop.price_from != price_from:
        prop.price_from = price_from
        changed_fields.append("price_from")
    if prop.has_valid_pricing != valid:
        prop.has_valid_pricing = valid
        changed_fields.append("has_valid_pricing")
    if changed_fields:
        await prop.save(update_fields=changed_fields)


async def recompute_all_pricing_cache(*, today: date | None = None) -> int:
    """Refresh the pricing cache for every property (nightly horizon recompute).

    Args:
        today: Override the start of the horizon (defaults to ``date.today()``).

    Returns:
        The number of properties processed.
    """
    from app.models import Property

    ids = cast("list[UUID]", await Property.all().values_list("id", flat=True))
    for pid in ids:
        await sync_pricing_cache(pid, today=today)
    return len(ids)
