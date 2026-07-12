"""Unit tests for the pure price resolver service.

No database or HTTP — the resolver takes pre-loaded ``PropertyDatePrice`` rows.
A night with no row is "unpriced" (source ``"unpriced"``, price 0); there is no
weekday lookup and no base-price fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.services.price_resolver import resolve_prices_sync

# ---------------------------------------------------------------------------
# Minimal stub — mirrors only the fields the resolver reads
# ---------------------------------------------------------------------------


@dataclass
class _DatePrice:
    date: date
    price: Decimal
    property_id: Any = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dates(results: list) -> list[date]:
    return [r.date for r in results]


def _prices(results: list) -> list[Decimal]:
    return [r.price for r in results]


def _sources(results: list) -> list[str]:
    return [r.source for r in results]


# ---------------------------------------------------------------------------
# Empty range
# ---------------------------------------------------------------------------


def test_empty_range_returns_nothing():
    result = resolve_prices_sync(
        start_date=date(2026, 6, 10),
        end_date=date(2026, 6, 10),
        date_prices=[],
    )
    assert result == []


def test_inverted_range_returns_nothing():
    result = resolve_prices_sync(
        start_date=date(2026, 6, 15),
        end_date=date(2026, 6, 10),
        date_prices=[],
    )
    assert result == []


# ---------------------------------------------------------------------------
# Unpriced nights (no rows)
# ---------------------------------------------------------------------------


def test_single_night_unpriced():
    result = resolve_prices_sync(
        start_date=date(2026, 6, 8),
        end_date=date(2026, 6, 9),
        date_prices=[],
    )
    assert len(result) == 1
    assert result[0].price == Decimal("0.00")
    assert result[0].source == "unpriced"
    assert result[0].label is None


def test_multi_night_unpriced():
    result = resolve_prices_sync(
        start_date=date(2026, 6, 8),
        end_date=date(2026, 6, 11),
        date_prices=[],
    )
    assert len(result) == 3
    assert all(r.price == Decimal("0.00") and r.source == "unpriced" for r in result)


def test_checkout_night_excluded():
    """end_date is the checkout day — should not appear in the result."""
    result = resolve_prices_sync(
        start_date=date(2026, 6, 8),
        end_date=date(2026, 6, 10),
        date_prices=[],
    )
    assert _dates(result) == [date(2026, 6, 8), date(2026, 6, 9)]


# ---------------------------------------------------------------------------
# Per-date rows
# ---------------------------------------------------------------------------


def test_priced_night_from_row():
    result = resolve_prices_sync(
        start_date=date(2026, 6, 8),
        end_date=date(2026, 6, 9),
        date_prices=[_DatePrice(date=date(2026, 6, 8), price=Decimal("75.00"))],
    )
    assert result[0].price == Decimal("75.00")
    assert result[0].source == "date"
    assert result[0].label is None


def test_row_applies_only_to_its_date():
    result = resolve_prices_sync(
        start_date=date(2026, 6, 8),
        end_date=date(2026, 6, 11),
        date_prices=[_DatePrice(date=date(2026, 6, 8), price=Decimal("75.00"))],
    )
    assert result[0].price == Decimal("75.00")
    assert result[0].source == "date"
    assert result[1].source == "unpriced"
    assert result[2].source == "unpriced"


def test_mixed_priced_and_unpriced():
    rows = [
        _DatePrice(date=date(2026, 6, 13), price=Decimal("90.00")),
        _DatePrice(date=date(2026, 6, 14), price=Decimal("120.00")),
    ]
    # Jun 13, 14 priced; Jun 15 unpriced
    result = resolve_prices_sync(
        start_date=date(2026, 6, 13),
        end_date=date(2026, 6, 16),
        date_prices=rows,
    )
    assert _prices(result) == [Decimal("90.00"), Decimal("120.00"), Decimal("0.00")]
    assert _sources(result) == ["date", "date", "unpriced"]


def test_rows_outside_range_ignored():
    rows = [
        _DatePrice(date=date(2026, 6, 1), price=Decimal("50.00")),
        _DatePrice(date=date(2026, 6, 20), price=Decimal("60.00")),
    ]
    result = resolve_prices_sync(
        start_date=date(2026, 6, 8),
        end_date=date(2026, 6, 10),
        date_prices=rows,
    )
    assert _sources(result) == ["unpriced", "unpriced"]


# ---------------------------------------------------------------------------
# Total
# ---------------------------------------------------------------------------


def test_total_calculation():
    from app.services.price_resolver import calculate_total

    nights = [
        type("R", (), {"price": Decimal("50.00")})(),
        type("R", (), {"price": Decimal("75.00")})(),
        type("R", (), {"price": Decimal("150.00")})(),
    ]
    assert calculate_total(nights) == Decimal("275.00")


def test_total_empty():
    from app.services.price_resolver import calculate_total

    assert calculate_total([]) == Decimal("0.00")


# ---------------------------------------------------------------------------
# Batch stay totals (search results)
# ---------------------------------------------------------------------------


class _AwaitableList:
    """Mimic a Tortoise QuerySet: awaiting or .order_by() yields the row list."""

    def __init__(self, items: list) -> None:
        self._items = items

    def order_by(self, *_args: Any) -> _AwaitableList:
        return self

    def __await__(self):
        async def _coro():
            return self._items

        return _coro().__await__()


def _stay_totals(property_ids, start, end, price_rows):
    import asyncio
    from unittest.mock import MagicMock, patch

    from app.services.price_resolver import compute_stay_totals

    with patch(
        "app.models.PropertyDatePrice.filter",
        MagicMock(return_value=_AwaitableList(price_rows)),
    ):
        return asyncio.run(compute_stay_totals(property_ids, start, end))


def test_stay_total_omits_unpriced_stay():
    """A stay with an unpriced night is omitted (not bookable)."""
    start, end = date(2026, 6, 8), date(2026, 6, 10)  # 2 nights, no rows
    totals = _stay_totals(["p1"], start, end, [])
    assert totals == {}


def test_stay_total_omits_when_partially_priced():
    """First night priced, second unpriced -> stay omitted."""
    start, end = date(2026, 6, 8), date(2026, 6, 10)
    row = _DatePrice(date=date(2026, 6, 8), price=Decimal("120.00"), property_id="p1")
    totals = _stay_totals(["p1"], start, end, [row])
    assert totals == {}


def test_stay_total_fully_priced_property():
    """A property priced on every night in the range gets a total."""
    start, end = date(2026, 6, 8), date(2026, 6, 10)  # Mon, Tue
    rows = [
        _DatePrice(date=date(2026, 6, 8), price=Decimal("30.00"), property_id="p2"),
        _DatePrice(date=date(2026, 6, 9), price=Decimal("40.00"), property_id="p2"),
    ]
    totals = _stay_totals(["p1", "p2"], start, end, rows)
    # p1 has no rows (unpriced) -> omitted. p2: 30 + 40 = 70.
    assert totals == {"p2": Decimal("70.00")}


def test_stay_total_empty_for_zero_nights():
    """Same-day check-in/out yields no totals."""
    d = date(2026, 6, 8)
    assert _stay_totals(["p1"], d, d, []) == {}
