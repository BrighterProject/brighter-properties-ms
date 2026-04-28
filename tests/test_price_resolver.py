"""Unit tests for the pure price resolver service.

No database or HTTP — resolver takes pre-loaded rule objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from app.services.price_resolver import resolve_prices_sync


# ---------------------------------------------------------------------------
# Minimal stubs — mirror only the fields the resolver reads
# ---------------------------------------------------------------------------


@dataclass
class _WeekdayRule:
    weekday: int
    price: Decimal


@dataclass
class _DateOverride:
    start_date: date
    end_date: date
    price: Decimal
    label: str | None
    created_at: Any = None  # used for ordering; higher index = later


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE = Decimal("50.00")


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
        base_price=BASE,
        start_date=date(2026, 6, 10),
        end_date=date(2026, 6, 10),
        weekday_rules=[],
        date_overrides=[],
    )
    assert result == []


def test_inverted_range_returns_nothing():
    result = resolve_prices_sync(
        base_price=BASE,
        start_date=date(2026, 6, 15),
        end_date=date(2026, 6, 10),
        weekday_rules=[],
        date_overrides=[],
    )
    assert result == []


# ---------------------------------------------------------------------------
# Base price only
# ---------------------------------------------------------------------------


def test_single_night_base():
    result = resolve_prices_sync(
        base_price=BASE,
        start_date=date(2026, 6, 8),  # Monday
        end_date=date(2026, 6, 9),
        weekday_rules=[],
        date_overrides=[],
    )
    assert len(result) == 1
    assert result[0].price == BASE
    assert result[0].source == "base"
    assert result[0].label is None


def test_multi_night_base():
    result = resolve_prices_sync(
        base_price=BASE,
        start_date=date(2026, 6, 8),
        end_date=date(2026, 6, 11),
        weekday_rules=[],
        date_overrides=[],
    )
    assert len(result) == 3
    assert all(r.price == BASE and r.source == "base" for r in result)


def test_checkout_night_excluded():
    """end_date is the checkout day — should not appear in the result."""
    result = resolve_prices_sync(
        base_price=BASE,
        start_date=date(2026, 6, 8),
        end_date=date(2026, 6, 10),
        weekday_rules=[],
        date_overrides=[],
    )
    assert _dates(result) == [date(2026, 6, 8), date(2026, 6, 9)]


# ---------------------------------------------------------------------------
# Weekday rules
# ---------------------------------------------------------------------------


def test_weekday_overrides_base():
    # June 8 2026 is Monday (weekday=0)
    result = resolve_prices_sync(
        base_price=BASE,
        start_date=date(2026, 6, 8),
        end_date=date(2026, 6, 9),
        weekday_rules=[_WeekdayRule(weekday=0, price=Decimal("75.00"))],
        date_overrides=[],
    )
    assert result[0].price == Decimal("75.00")
    assert result[0].source == "weekday"


def test_weekday_rule_applies_only_to_matching_day():
    # Jun 8=Mon(0), Jun 9=Tue(1), Jun 10=Wed(2)
    result = resolve_prices_sync(
        base_price=BASE,
        start_date=date(2026, 6, 8),
        end_date=date(2026, 6, 11),
        weekday_rules=[_WeekdayRule(weekday=0, price=Decimal("75.00"))],
        date_overrides=[],
    )
    assert result[0].price == Decimal("75.00")
    assert result[0].source == "weekday"
    assert result[1].price == BASE
    assert result[1].source == "base"
    assert result[2].price == BASE


def test_multiple_weekday_rules():
    # Weekend: Sat=5, Sun=6
    rules = [
        _WeekdayRule(weekday=5, price=Decimal("90.00")),
        _WeekdayRule(weekday=6, price=Decimal("90.00")),
    ]
    # Jun 13=Sat, Jun 14=Sun, Jun 15=Mon
    result = resolve_prices_sync(
        base_price=BASE,
        start_date=date(2026, 6, 13),
        end_date=date(2026, 6, 16),
        weekday_rules=rules,
        date_overrides=[],
    )
    assert _prices(result) == [Decimal("90.00"), Decimal("90.00"), BASE]
    assert _sources(result) == ["weekday", "weekday", "base"]


# ---------------------------------------------------------------------------
# Date overrides
# ---------------------------------------------------------------------------


def test_date_override_beats_base():
    # Single-day override
    ov = _DateOverride(
        start_date=date(2026, 12, 25),
        end_date=date(2026, 12, 25),
        price=Decimal("150.00"),
        label="Christmas",
    )
    result = resolve_prices_sync(
        base_price=BASE,
        start_date=date(2026, 12, 24),
        end_date=date(2026, 12, 27),
        weekday_rules=[],
        date_overrides=[ov],
    )
    prices_by_date = {r.date: r for r in result}
    assert prices_by_date[date(2026, 12, 24)].source == "base"
    assert prices_by_date[date(2026, 12, 25)].price == Decimal("150.00")
    assert prices_by_date[date(2026, 12, 25)].source == "date_override"
    assert prices_by_date[date(2026, 12, 25)].label == "Christmas"
    assert prices_by_date[date(2026, 12, 26)].source == "base"


def test_date_override_beats_weekday_rule():
    """Override priority: date_override > weekday > base."""
    # Dec 25 2026 is a Friday (weekday=4)
    rules = [_WeekdayRule(weekday=4, price=Decimal("80.00"))]
    ov = _DateOverride(
        start_date=date(2026, 12, 25),
        end_date=date(2026, 12, 25),
        price=Decimal("200.00"),
        label="Christmas",
    )
    result = resolve_prices_sync(
        base_price=BASE,
        start_date=date(2026, 12, 25),
        end_date=date(2026, 12, 26),
        weekday_rules=rules,
        date_overrides=[ov],
    )
    assert result[0].price == Decimal("200.00")
    assert result[0].source == "date_override"


def test_multi_day_override_range():
    ov = _DateOverride(
        start_date=date(2026, 12, 24),
        end_date=date(2026, 12, 26),
        price=Decimal("150.00"),
        label="Christmas Eve+",
    )
    result = resolve_prices_sync(
        base_price=BASE,
        start_date=date(2026, 12, 23),
        end_date=date(2026, 12, 28),
        weekday_rules=[],
        date_overrides=[ov],
    )
    prices_by_date = {r.date: r for r in result}
    assert prices_by_date[date(2026, 12, 23)].source == "base"
    assert prices_by_date[date(2026, 12, 24)].source == "date_override"
    assert prices_by_date[date(2026, 12, 25)].source == "date_override"
    assert prices_by_date[date(2026, 12, 26)].source == "date_override"
    assert prices_by_date[date(2026, 12, 27)].source == "base"


# ---------------------------------------------------------------------------
# Overlapping overrides — last created wins
# ---------------------------------------------------------------------------


def test_overlapping_overrides_last_created_wins():
    """When two overrides cover the same date, the one later in the list wins."""
    early = _DateOverride(
        start_date=date(2026, 12, 25),
        end_date=date(2026, 12, 25),
        price=Decimal("100.00"),
        label="Early",
    )
    late = _DateOverride(
        start_date=date(2026, 12, 25),
        end_date=date(2026, 12, 25),
        price=Decimal("200.00"),
        label="Late",
    )
    # Pass early then late — late should win
    result = resolve_prices_sync(
        base_price=BASE,
        start_date=date(2026, 12, 25),
        end_date=date(2026, 12, 26),
        weekday_rules=[],
        date_overrides=[early, late],
    )
    assert result[0].price == Decimal("200.00")
    assert result[0].label == "Late"


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
