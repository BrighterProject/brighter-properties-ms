"""Tests for base-price derivation from the pricing calendar.

The base ``price_per_night`` is no longer entered by owners; it is derived as the
cheapest configured nightly rate and recomputed whenever pricing changes.
All model access is patched — no database required.
"""

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.base_price import compute_derived_base_price, sync_base_price


class _AwaitableList:
    """Mimic a Tortoise QuerySet: awaiting it yields the row list."""

    def __init__(self, items: list) -> None:
        self._items = items

    def __await__(self):
        async def _coro():
            return self._items

        return _coro().__await__()


def _compute(weekday_prices: list[str], override_prices: list[str]):
    weekday_rows = [SimpleNamespace(price=Decimal(p)) for p in weekday_prices]
    override_rows = [SimpleNamespace(price=Decimal(p)) for p in override_prices]
    with (
        patch(
            "app.models.PropertyWeekdayPrice.filter",
            MagicMock(return_value=_AwaitableList(weekday_rows)),
        ),
        patch(
            "app.models.PropertyDatePriceOverride.filter",
            MagicMock(return_value=_AwaitableList(override_rows)),
        ),
    ):
        return asyncio.run(compute_derived_base_price(uuid4()))


def test_no_pricing_returns_none():
    """With no weekday prices and no overrides, nothing can be derived."""
    assert _compute([], []) is None


def test_min_across_weekdays():
    """Base price is the cheapest weekday price when no overrides exist."""
    assert _compute(["90.00", "70.00", "120.00"], []) == Decimal("70.00")


def test_min_across_overrides():
    """Base price is the cheapest override when no weekday prices exist."""
    assert _compute([], ["150.00", "60.00"]) == Decimal("60.00")


def test_min_spans_both_sources():
    """The minimum considers weekday prices and overrides together."""
    assert _compute(["90.00"], ["150.00", "45.50"]) == Decimal("45.50")


def test_sync_persists_when_changed():
    """sync_base_price saves the derived value when it differs from the stored one."""
    prop = MagicMock()
    prop.price_per_night = Decimal("999.00")
    prop.save = AsyncMock()
    with (
        patch(
            "app.services.base_price.compute_derived_base_price",
            new_callable=AsyncMock,
            return_value=Decimal("70.00"),
        ),
        patch("app.models.Property.get_or_none", new_callable=AsyncMock, return_value=prop),
    ):
        result = asyncio.run(sync_base_price(uuid4()))
    assert result == Decimal("70.00")
    assert prop.price_per_night == Decimal("70.00")
    prop.save.assert_awaited_once_with(update_fields=["price_per_night"])


def test_sync_noop_when_unchanged():
    """No save is issued when the derived price already matches."""
    prop = MagicMock()
    prop.price_per_night = Decimal("70.00")
    prop.save = AsyncMock()
    with (
        patch(
            "app.services.base_price.compute_derived_base_price",
            new_callable=AsyncMock,
            return_value=Decimal("70.00"),
        ),
        patch("app.models.Property.get_or_none", new_callable=AsyncMock, return_value=prop),
    ):
        result = asyncio.run(sync_base_price(uuid4()))
    assert result == Decimal("70.00")
    prop.save.assert_not_awaited()


def test_sync_leaves_stored_value_when_no_pricing():
    """With no pricing to derive from, the stored base price is left untouched."""
    prop = MagicMock()
    prop.price_per_night = Decimal("50.00")
    prop.save = AsyncMock()
    with (
        patch(
            "app.services.base_price.compute_derived_base_price",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("app.models.Property.get_or_none", new_callable=AsyncMock, return_value=prop),
    ):
        result = asyncio.run(sync_base_price(uuid4()))
    assert result is None
    prop.save.assert_not_awaited()
