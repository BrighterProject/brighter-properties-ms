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

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from app import settings


def compute_price_from(
    weekday_rules: list[Any], date_overrides: list[Any], *, today: date
) -> Decimal | None:
    """Return the cheapest currently-bookable nightly price, or ``None``.

    Expired overrides are excluded so a long-past discount can't perpetually
    drag the public "from X" price below today's real rates. ``end_date`` is
    inclusive (matches ``price_resolver`` / ``coverage``), so an override whose
    last night is ``today`` still counts.

    Args:
        weekday_rules: The property's ``PropertyWeekdayPrice`` rows.
        date_overrides: The property's ``PropertyDatePriceOverride`` rows.
        today: Anything with ``end_date < today`` is treated as expired.

    Returns:
        The minimum active configured price across both sources, or ``None``
        when the property has no currently-bookable pricing.
    """
    prices: list[Decimal] = [w.price for w in weekday_rules]
    prices += [o.price for o in date_overrides if o.end_date >= today]
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

    today = today or date.today()
    price_from = compute_price_from(weekday_rules, date_overrides, today=today)
    valid = has_valid_pricing(
        weekday_rules,
        date_overrides,
        today=today,
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

    Uses three bulk queries (properties + all weekday rules + all overrides)
    grouped in memory, then a single ``bulk_update`` of only the rows that
    changed — O(1) round-trips instead of the ~3N sequential queries a
    per-property loop would issue.

    Args:
        today: Override the start of the horizon (defaults to ``date.today()``).

    Returns:
        The number of properties processed.
    """
    from app.models import Property, PropertyDatePriceOverride, PropertyWeekdayPrice

    today = today or date.today()
    horizon_days = settings.booking_window_days

    properties = await Property.all()
    if not properties:
        return 0

    # Tortoise exposes the FK column as ``.property_id`` at runtime; typed as Any
    # so the grouping below type-checks (mirrors ``price_resolver``).
    weekday_rows: list[Any] = await PropertyWeekdayPrice.all()
    override_rows: list[Any] = await PropertyDatePriceOverride.all()

    weekdays_by_prop: defaultdict[UUID, list[Any]] = defaultdict(list)
    for weekday in weekday_rows:
        weekdays_by_prop[weekday.property_id].append(weekday)
    overrides_by_prop: defaultdict[UUID, list[Any]] = defaultdict(list)
    for override in override_rows:
        overrides_by_prop[override.property_id].append(override)

    changed: list[Any] = []
    for prop in properties:
        weekday_rules = weekdays_by_prop.get(prop.id, [])
        date_overrides = overrides_by_prop.get(prop.id, [])
        price_from = compute_price_from(weekday_rules, date_overrides, today=today)
        valid = has_valid_pricing(
            weekday_rules,
            date_overrides,
            today=today,
            horizon_days=horizon_days,
        )
        if prop.price_from != price_from or prop.has_valid_pricing != valid:
            prop.price_from = price_from
            prop.has_valid_pricing = valid
            changed.append(prop)

    if changed:
        await Property.bulk_update(changed, fields=["price_from", "has_valid_pricing"])
    return len(properties)
