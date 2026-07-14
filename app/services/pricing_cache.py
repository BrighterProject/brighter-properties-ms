"""Maintain a property's denormalized pricing cache.

Two system-owned fields on ``Property`` are kept in sync with the per-date
pricing calendar (``PropertyDatePrice``); neither is ever owner input:

* ``price_from`` — the cheapest priced night within the rolling booking horizon
  (``BOOKING_WINDOW_DAYS`` from today). ``None`` when no night in the horizon is
  priced. Expired/beyond-horizon rows don't count, so a long-past cheap night
  can't drag the public "from X" price below today's real rates.
* ``has_valid_pricing`` — whether at least one night within that same horizon is
  priced. Drives whether the property is publicly listable.

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
    date_prices: list[Any], *, today: date, horizon_days: int
) -> Decimal | None:
    """Return the cheapest priced night within the horizon, or ``None``.

    Args:
        date_prices: The property's ``PropertyDatePrice`` rows.
        today: First day of the rolling horizon (inclusive).
        horizon_days: Length of the horizon in days.

    Returns:
        The minimum price across nights in ``[today, today + horizon_days)``,
        or ``None`` when no such night is priced.
    """
    if horizon_days <= 0:
        return None
    end = today + timedelta(days=horizon_days)  # exclusive
    prices = [p.price for p in date_prices if today <= p.date < end]
    return min(prices) if prices else None


def has_valid_pricing(
    date_prices: list[Any],
    *,
    today: date,
    horizon_days: int,
) -> bool:
    """Return whether any night in ``[today, today + horizon_days)`` is priced.

    Args:
        date_prices: The property's ``PropertyDatePrice`` rows.
        today: First day of the rolling horizon (inclusive).
        horizon_days: Length of the horizon in days.

    Returns:
        ``True`` if at least one priced night falls within the horizon.
    """
    if horizon_days <= 0:
        return False
    end = today + timedelta(days=horizon_days)  # exclusive
    return any(today <= p.date < end for p in date_prices)


async def sync_pricing_cache(property_id: UUID, *, today: date | None = None) -> None:
    """Recompute and persist ``price_from`` and ``has_valid_pricing``.

    Fetches the property's pricing calendar once and writes both cache fields,
    saving only when a value actually changed.

    Args:
        property_id: Property whose cache to refresh.
        today: Override the start of the horizon (defaults to ``date.today()``).
    """
    from app.models import Property, PropertyDatePrice

    prop = await Property.get_or_none(id=property_id)
    if prop is None:
        return

    today = today or date.today()
    horizon_days = settings.booking_window_days
    date_prices = await PropertyDatePrice.filter(
        property_id=property_id,
        date__gte=today,
        date__lt=today + timedelta(days=horizon_days),
    )

    price_from = compute_price_from(date_prices, today=today, horizon_days=horizon_days)
    valid = has_valid_pricing(date_prices, today=today, horizon_days=horizon_days)

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

    Uses two bulk queries (properties + all in-horizon date prices) grouped in
    memory, then a single ``bulk_update`` of only the rows that changed — O(1)
    round-trips instead of the ~2N sequential queries a per-property loop would
    issue.

    Args:
        today: Override the start of the horizon (defaults to ``date.today()``).

    Returns:
        The number of properties processed.
    """
    from app.models import Property, PropertyDatePrice

    today = today or date.today()
    horizon_days = settings.booking_window_days

    properties = await Property.all()
    if not properties:
        return 0

    # Only in-horizon rows matter for both projections; scope the bulk query to
    # the horizon so past/far-future rows never enter memory. Tortoise exposes
    # the FK column as ``.property_id`` at runtime; typed as Any so the grouping
    # below type-checks (mirrors ``price_resolver``).
    price_rows: list[Any] = await PropertyDatePrice.filter(
        date__gte=today,
        date__lt=today + timedelta(days=horizon_days),
    )

    prices_by_prop: defaultdict[UUID, list[Any]] = defaultdict(list)
    for row in price_rows:
        prices_by_prop[row.property_id].append(row)

    changed: list[Any] = []
    for prop in properties:
        date_prices = prices_by_prop.get(prop.id, [])
        price_from = compute_price_from(
            date_prices, today=today, horizon_days=horizon_days
        )
        valid = has_valid_pricing(date_prices, today=today, horizon_days=horizon_days)
        if prop.price_from != price_from or prop.has_valid_pricing != valid:
            prop.price_from = price_from
            prop.has_valid_pricing = valid
            changed.append(prop)

    if changed:
        await Property.bulk_update(changed, fields=["price_from", "has_valid_pricing"])
    return len(properties)
