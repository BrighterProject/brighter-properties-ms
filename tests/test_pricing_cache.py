"""Tests for the denormalized pricing cache (price_from + has_valid_pricing).

``price_from`` and ``has_valid_pricing`` are system-owned projections of the
pricing calendar, never owner input. The pure helpers are tested directly; the
persisting ``sync_pricing_cache`` is tested with the model layer patched — no
database required.
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


def _weekday(price: str) -> SimpleNamespace:
    return SimpleNamespace(price=Decimal(price))


def _override(price: str, start: date, end: date) -> SimpleNamespace:
    return SimpleNamespace(price=Decimal(price), start_date=start, end_date=end)


TODAY = date(2026, 7, 11)
HORIZON = 180


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
    assert compute_price_from([], [], today=TODAY) is None


def test_price_from_min_across_weekdays():
    assert compute_price_from(
        [_weekday("90"), _weekday("70")], [], today=TODAY
    ) == Decimal("70")


def test_price_from_min_across_overrides():
    d = TODAY + timedelta(days=20)
    overrides = [_override("150", d, d), _override("60", d, d)]
    assert compute_price_from([], overrides, today=TODAY) == Decimal("60")


def test_price_from_spans_both_sources():
    d = TODAY + timedelta(days=20)
    assert compute_price_from(
        [_weekday("90")], [_override("45.50", d, d)], today=TODAY
    ) == Decimal("45.50")


def test_price_from_excludes_expired_overrides():
    # A cheap past special must not drag the public "from X" price down.
    past = _override("10", TODAY - timedelta(days=90), TODAY - timedelta(days=60))
    assert compute_price_from([_weekday("90")], [past], today=TODAY) == Decimal("90")


def test_price_from_includes_override_ending_today():
    # end_date is inclusive: an override whose last night is today still counts.
    ending = _override("40", TODAY - timedelta(days=3), TODAY)
    assert compute_price_from([_weekday("90")], [ending], today=TODAY) == Decimal("40")


# ---------------------------------------------------------------------------
# has_valid_pricing
# ---------------------------------------------------------------------------


def test_valid_false_without_pricing():
    assert has_valid_pricing([], [], today=TODAY, horizon_days=HORIZON) is False


def test_valid_true_with_any_weekday_rule():
    # Weekday rules recur weekly, so they always cover a day in the horizon.
    assert has_valid_pricing([_weekday("50")], [], today=TODAY, horizon_days=HORIZON)


def test_valid_true_when_override_intersects_horizon():
    inside = TODAY + timedelta(days=30)
    assert has_valid_pricing(
        [], [_override("50", inside, inside)], today=TODAY, horizon_days=HORIZON
    )


def test_valid_false_when_all_overrides_in_past():
    past = TODAY - timedelta(days=5)
    assert (
        has_valid_pricing(
            [], [_override("50", past, past)], today=TODAY, horizon_days=HORIZON
        )
        is False
    )


def test_valid_false_when_override_beyond_horizon():
    beyond = TODAY + timedelta(days=HORIZON + 10)
    assert (
        has_valid_pricing(
            [], [_override("50", beyond, beyond)], today=TODAY, horizon_days=HORIZON
        )
        is False
    )


def test_valid_false_when_horizon_zero():
    assert has_valid_pricing([_weekday("50")], [], today=TODAY, horizon_days=0) is False


# ---------------------------------------------------------------------------
# sync_pricing_cache
# ---------------------------------------------------------------------------


def _run_sync(prop, weekday_rows, override_rows):
    with (
        patch(
            "app.models.Property.get_or_none",
            new_callable=AsyncMock,
            return_value=prop,
        ),
        patch(
            "app.models.PropertyWeekdayPrice.filter",
            MagicMock(return_value=_AwaitableList(weekday_rows)),
        ),
        patch(
            "app.models.PropertyDatePriceOverride.filter",
            MagicMock(return_value=_AwaitableList(override_rows)),
        ),
    ):
        asyncio.run(sync_pricing_cache(uuid4(), today=TODAY))


def test_sync_persists_both_fields_when_changed():
    prop = MagicMock()
    prop.price_from = Decimal("999.00")
    prop.has_valid_pricing = False
    prop.save = AsyncMock()
    _run_sync(prop, [_weekday("70")], [])
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
    _run_sync(prop, [], [])
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
    _run_sync(prop, [_weekday("70")], [])
    prop.save.assert_not_awaited()


def test_sync_ignores_missing_property():
    with patch(
        "app.models.Property.get_or_none", new_callable=AsyncMock, return_value=None
    ):
        # No weekday/override access should be required when the property is gone.
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


def _weekday_row(pid, price: str) -> SimpleNamespace:
    return SimpleNamespace(property_id=pid, price=Decimal(price))


def _run_recompute(properties, weekday_rows, override_rows) -> tuple[int, list]:
    bulk_update = AsyncMock()
    with (
        patch(
            "app.models.Property.all",
            MagicMock(return_value=_AwaitableList(properties)),
        ),
        patch(
            "app.models.PropertyWeekdayPrice.all",
            MagicMock(return_value=_AwaitableList(weekday_rows)),
        ),
        patch(
            "app.models.PropertyDatePriceOverride.all",
            MagicMock(return_value=_AwaitableList(override_rows)),
        ),
        patch("app.models.Property.bulk_update", bulk_update),
    ):
        count = asyncio.run(recompute_all_pricing_cache(today=TODAY))
    return count, bulk_update.await_args_list


def test_recompute_bulk_updates_only_changed_properties():
    p1 = uuid4()  # needs update: no cache set yet, has a weekday rule
    p2 = uuid4()  # already correct: skipped
    props = [_prop(p1, None, False), _prop(p2, Decimal("50"), True)]
    weekdays = [_weekday_row(p1, "80"), _weekday_row(p2, "50")]
    count, calls = _run_recompute(props, weekdays, [])

    assert count == 2
    assert len(calls) == 1
    updated = calls[0].args[0]
    assert [p.id for p in updated] == [p1]
    assert updated[0].price_from == Decimal("80")
    assert updated[0].has_valid_pricing is True
    assert calls[0].kwargs["fields"] == ["price_from", "has_valid_pricing"]


def test_recompute_no_properties_skips_bulk_update():
    count, calls = _run_recompute([], [], [])
    assert count == 0
    assert calls == []
