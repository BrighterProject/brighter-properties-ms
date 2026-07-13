"""Tests for the denormalized pricing cache (price_from + has_valid_pricing).

``price_from`` and ``has_valid_pricing`` are system-owned projections of the
per-date pricing calendar, never owner input. The pure helpers are tested
directly; the persisting ``sync_pricing_cache`` is tested with the model layer
patched — no database required.
"""

import asyncio
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.pricing_cache import (
    compute_price_from,
    has_valid_pricing,
    recompute_all_pricing_cache,
    sync_pricing_cache,
)

TODAY = date(2026, 7, 11)
HORIZON = 180


def _price(price: str, offset: int, pid=None) -> SimpleNamespace:
    """A per-date row ``offset`` days from TODAY."""
    return SimpleNamespace(
        price=Decimal(price), date=TODAY + timedelta(days=offset), property_id=pid
    )


class _AwaitableList:
    """Mimic a Tortoise QuerySet: awaiting it yields the row list."""

    def __init__(self, items: list) -> None:
        self._items = items

    def __await__(self):
        async def _coro():
            return self._items

        return _coro().__await__()


# ---------------------------------------------------------------------------
# compute_price_from
# ---------------------------------------------------------------------------


def test_price_from_none_when_no_pricing():
    assert compute_price_from([], today=TODAY, horizon_days=HORIZON) is None


def test_price_from_min_across_horizon():
    rows = [_price("90", 5), _price("70", 20)]
    assert compute_price_from(rows, today=TODAY, horizon_days=HORIZON) == Decimal("70")


def test_price_from_excludes_past_nights():
    # A cheap past night must not drag the public "from X" price down.
    rows = [_price("10", -30), _price("90", 5)]
    assert compute_price_from(rows, today=TODAY, horizon_days=HORIZON) == Decimal("90")


def test_price_from_excludes_beyond_horizon():
    rows = [_price("40", HORIZON + 10), _price("90", 5)]
    assert compute_price_from(rows, today=TODAY, horizon_days=HORIZON) == Decimal("90")


def test_price_from_includes_night_today():
    # Horizon is inclusive of today.
    rows = [_price("40", 0), _price("90", 5)]
    assert compute_price_from(rows, today=TODAY, horizon_days=HORIZON) == Decimal("40")


def test_price_from_none_when_horizon_zero():
    assert compute_price_from([_price("50", 0)], today=TODAY, horizon_days=0) is None


# ---------------------------------------------------------------------------
# has_valid_pricing
# ---------------------------------------------------------------------------


def test_valid_false_without_pricing():
    assert has_valid_pricing([], today=TODAY, horizon_days=HORIZON) is False


def test_valid_true_when_night_in_horizon():
    assert has_valid_pricing([_price("50", 30)], today=TODAY, horizon_days=HORIZON)


def test_valid_false_when_all_nights_in_past():
    assert (
        has_valid_pricing([_price("50", -5)], today=TODAY, horizon_days=HORIZON)
        is False
    )


def test_valid_false_when_night_beyond_horizon():
    assert (
        has_valid_pricing(
            [_price("50", HORIZON + 10)], today=TODAY, horizon_days=HORIZON
        )
        is False
    )


def test_valid_false_when_horizon_zero():
    assert has_valid_pricing([_price("50", 0)], today=TODAY, horizon_days=0) is False


# ---------------------------------------------------------------------------
# sync_pricing_cache
# ---------------------------------------------------------------------------


def _run_sync(prop, price_rows):
    with (
        patch(
            "app.models.Property.get_or_none",
            new_callable=AsyncMock,
            return_value=prop,
        ),
        patch(
            "app.models.PropertyDatePrice.filter",
            MagicMock(return_value=_AwaitableList(price_rows)),
        ),
    ):
        asyncio.run(sync_pricing_cache(uuid4(), today=TODAY))


def test_sync_persists_both_fields_when_changed():
    prop = MagicMock()
    prop.price_from = Decimal("999.00")
    prop.has_valid_pricing = False
    prop.save = AsyncMock()
    _run_sync(prop, [_price("70", 5)])
    assert prop.price_from == Decimal("70")
    assert prop.has_valid_pricing is True
    prop.save.assert_awaited_once_with(
        update_fields=["price_from", "has_valid_pricing"]
    )


def test_sync_clears_cache_when_pricing_removed():
    prop = MagicMock()
    prop.price_from = Decimal("70.00")
    prop.has_valid_pricing = True
    prop.save = AsyncMock()
    _run_sync(prop, [])
    assert prop.price_from is None
    assert prop.has_valid_pricing is False
    prop.save.assert_awaited_once_with(
        update_fields=["price_from", "has_valid_pricing"]
    )


def test_sync_noop_when_unchanged():
    prop = MagicMock()
    prop.price_from = Decimal("70")
    prop.has_valid_pricing = True
    prop.save = AsyncMock()
    _run_sync(prop, [_price("70", 5)])
    prop.save.assert_not_awaited()


def test_sync_ignores_missing_property():
    with patch(
        "app.models.Property.get_or_none", new_callable=AsyncMock, return_value=None
    ):
        asyncio.run(sync_pricing_cache(uuid4(), today=TODAY))


# ---------------------------------------------------------------------------
# recompute_all_pricing_cache
# ---------------------------------------------------------------------------


def _prop(pid, price_from, valid) -> MagicMock:
    prop = MagicMock()
    prop.id = pid
    prop.price_from = price_from
    prop.has_valid_pricing = valid
    return prop


def _run_recompute(properties, price_rows) -> tuple[int, list]:
    bulk_update = AsyncMock()
    with (
        patch(
            "app.models.Property.all",
            MagicMock(return_value=_AwaitableList(properties)),
        ),
        patch(
            "app.models.PropertyDatePrice.filter",
            MagicMock(return_value=_AwaitableList(price_rows)),
        ),
        patch("app.models.Property.bulk_update", bulk_update),
    ):
        count = asyncio.run(recompute_all_pricing_cache(today=TODAY))
    return count, bulk_update.await_args_list


def test_recompute_bulk_updates_only_changed_properties():
    p1 = uuid4()  # needs update: no cache set yet, has a priced night
    p2 = uuid4()  # already correct: skipped
    props = [_prop(p1, None, False), _prop(p2, Decimal("50"), True)]
    rows = [_price("80", 5, pid=p1), _price("50", 5, pid=p2)]
    count, calls = _run_recompute(props, rows)

    assert count == 2
    assert len(calls) == 1
    updated = calls[0].args[0]
    assert [p.id for p in updated] == [p1]
    assert updated[0].price_from == Decimal("80")
    assert updated[0].has_valid_pricing is True
    assert calls[0].kwargs["fields"] == ["price_from", "has_valid_pricing"]


def test_recompute_no_properties_skips_bulk_update():
    count, calls = _run_recompute([], [])
    assert count == 0
    assert calls == []
