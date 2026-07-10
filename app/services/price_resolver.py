"""Pure price resolution logic for pseudo-dynamic pricing.

Priority: date_override > weekday_rule > base_price.
Overlapping date overrides: last element in the list wins (caller must pass them
ordered by created_at ascending so the last one is the most recently created).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, NamedTuple, Protocol


class _HasWeekday(Protocol):
    weekday: int
    price: Decimal


class _HasDateRange(Protocol):
    start_date: date
    end_date: date
    price: Decimal
    label: str | None


class ResolvedNight(NamedTuple):
    date: date
    price: Decimal
    source: str  # "base" | "weekday" | "date_override"
    label: str | None


def resolve_prices_sync(
    *,
    base_price: Decimal,
    start_date: date,
    end_date: date,
    weekday_rules: list[Any],
    date_overrides: list[Any],
) -> list[ResolvedNight]:
    """Resolve per-night prices for [start_date, end_date).

    ``end_date`` is the checkout day and is excluded from the result.
    ``date_overrides`` must be ordered by ``created_at`` ascending so that
    the last matching entry is the most recently created (wins on overlap).
    """
    num_nights = (end_date - start_date).days
    if num_nights <= 0:
        return []

    by_weekday: dict[int, Decimal] = {r.weekday: r.price for r in weekday_rules}

    results: list[ResolvedNight] = []
    for i in range(num_nights):
        night = start_date + timedelta(days=i)

        matching = [
            ov for ov in date_overrides if ov.start_date <= night <= ov.end_date
        ]
        if matching:
            best = matching[-1]
            results.append(
                ResolvedNight(
                    date=night,
                    price=best.price,
                    source="date_override",
                    label=best.label,
                )
            )
        elif night.weekday() in by_weekday:
            results.append(
                ResolvedNight(
                    date=night,
                    price=by_weekday[night.weekday()],
                    source="weekday",
                    label=None,
                )
            )
        else:
            results.append(
                ResolvedNight(date=night, price=base_price, source="base", label=None)
            )

    return results


async def resolve_prices_for_property(
    property_id: Any,
    base_price: Decimal,
    start_date: date,
    end_date: date,
) -> list[ResolvedNight]:
    """Load rules from DB and resolve prices for a property."""
    from app.models import PropertyDatePriceOverride, PropertyWeekdayPrice

    weekday_rules = await PropertyWeekdayPrice.filter(property_id=property_id).order_by(
        "weekday"
    )
    date_overrides = await PropertyDatePriceOverride.filter(
        property_id=property_id,
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).order_by("created_at")

    return resolve_prices_sync(
        base_price=base_price,
        start_date=start_date,
        end_date=end_date,
        weekday_rules=list(weekday_rules),
        date_overrides=list(date_overrides),
    )


def calculate_total(nights: list[Any]) -> Decimal:
    """Sum night prices. Returns 0.00 for empty input."""
    return sum((n.price for n in nights), Decimal("0.00"))


async def compute_stay_totals(
    property_ids: list[Any],
    start_date: date,
    end_date: date,
    base_prices: dict[Any, Decimal],
) -> dict[Any, Decimal]:
    """Compute the stay total for each property over ``[start_date, end_date)``.

    Batch-loads weekday rules and date overrides for all given properties in two
    queries (no N+1) and resolves each stay independently.

    Args:
        property_ids: Properties to price.
        start_date: Check-in date (inclusive).
        end_date: Checkout date (excluded from the nightly sum).
        base_prices: Per-property fallback price for nights with no rule.

    Returns:
        A ``{property_id: total}`` mapping. Properties with no priced nights
        still get a total computed from their base price.
    """
    from collections import defaultdict

    from app.models import PropertyDatePriceOverride, PropertyWeekdayPrice

    if not property_ids or (end_date - start_date).days <= 0:
        return {}

    # Tortoise exposes the FK column as ``.property_id`` at runtime; typed as Any
    # so the grouping below type-checks.
    weekday_rows: list[Any] = await PropertyWeekdayPrice.filter(
        property_id__in=property_ids
    )
    override_rows: list[Any] = await PropertyDatePriceOverride.filter(
        property_id__in=property_ids,
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).order_by("created_at")

    weekdays_by_prop: dict[Any, list] = defaultdict(list)
    for w in weekday_rows:
        weekdays_by_prop[w.property_id].append(w)
    overrides_by_prop: dict[Any, list] = defaultdict(list)
    for o in override_rows:
        overrides_by_prop[o.property_id].append(o)

    totals: dict[Any, Decimal] = {}
    for pid in property_ids:
        nights = resolve_prices_sync(
            base_price=base_prices.get(pid, Decimal("0")),
            start_date=start_date,
            end_date=end_date,
            weekday_rules=weekdays_by_prop.get(pid, []),
            date_overrides=overrides_by_prop.get(pid, []),
        )
        totals[pid] = calculate_total(nights)
    return totals
