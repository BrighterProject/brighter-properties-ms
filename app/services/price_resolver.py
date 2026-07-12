"""Pure price resolution logic for per-date pricing.

A night's price comes solely from its ``PropertyDatePrice`` row. A night with no
row is "unpriced" (source ``"unpriced"``, price 0) — there is no weekday lookup
and no base-price fallback. Callers that require a bookable stay must reject any
result containing an unpriced night.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, NamedTuple, Protocol


class _HasDatePrice(Protocol):
    date: date
    price: Decimal


class ResolvedNight(NamedTuple):
    date: date
    price: Decimal
    source: str  # "date" | "unpriced"
    label: str | None


def resolve_prices_sync(
    *,
    start_date: date,
    end_date: date,
    date_prices: list[Any],
) -> list[ResolvedNight]:
    """Resolve per-night prices for ``[start_date, end_date)``.

    ``end_date`` is the checkout day and is excluded from the result.

    Nights with a ``PropertyDatePrice`` row are priced (``source="date"``);
    nights without one are returned with ``source="unpriced"`` and price ``0``.
    """
    num_nights = (end_date - start_date).days
    if num_nights <= 0:
        return []

    by_date: dict[date, Decimal] = {p.date: p.price for p in date_prices}

    results: list[ResolvedNight] = []
    for i in range(num_nights):
        night = start_date + timedelta(days=i)
        price = by_date.get(night)
        if price is not None:
            results.append(ResolvedNight(night, price, "date", None))
        else:
            results.append(ResolvedNight(night, Decimal("0.00"), "unpriced", None))

    return results


async def resolve_prices_for_property(
    property_id: Any,
    start_date: date,
    end_date: date,
) -> list[ResolvedNight]:
    """Load per-date rows from DB and resolve prices for a property."""
    from app.models import PropertyDatePrice

    date_prices = await PropertyDatePrice.filter(
        property_id=property_id,
        date__gte=start_date,
        date__lt=end_date,
    )

    return resolve_prices_sync(
        start_date=start_date,
        end_date=end_date,
        date_prices=list(date_prices),
    )


def calculate_total(nights: list[Any]) -> Decimal:
    """Sum night prices. Returns 0.00 for empty input."""
    return sum((n.price for n in nights), Decimal("0.00"))


async def compute_stay_totals(
    property_ids: list[Any],
    start_date: date,
    end_date: date,
) -> dict[Any, Decimal]:
    """Compute the stay total for each property over ``[start_date, end_date)``.

    Batch-loads the per-date rows for all given properties in one query (no N+1)
    and resolves each stay independently.

    Args:
        property_ids: Properties to price.
        start_date: Check-in date (inclusive).
        end_date: Checkout date (excluded from the nightly sum).

    Returns:
        A ``{property_id: total}`` mapping. Properties whose stay includes an
        unpriced night are omitted (the stay is not fully priced, so no total
        can be shown).
    """
    from collections import defaultdict

    from app.models import PropertyDatePrice

    if not property_ids or (end_date - start_date).days <= 0:
        return {}

    # Tortoise exposes the FK column as ``.property_id`` at runtime; typed as Any
    # so the grouping below type-checks.
    price_rows: list[Any] = await PropertyDatePrice.filter(
        property_id__in=property_ids,
        date__gte=start_date,
        date__lt=end_date,
    )

    prices_by_prop: dict[Any, list] = defaultdict(list)
    for row in price_rows:
        prices_by_prop[row.property_id].append(row)

    totals: dict[Any, Decimal] = {}
    for pid in property_ids:
        nights = resolve_prices_sync(
            start_date=start_date,
            end_date=end_date,
            date_prices=prices_by_prop.get(pid, []),
        )
        # A stay with any unpriced night is not bookable — omit its total.
        if any(n.source == "unpriced" for n in nights):
            continue
        totals[pid] = calculate_total(nights)
    return totals
