"""Tests for price-gap availability synthesis (unpriced day = unavailable)."""

import asyncio
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.availability import PRICE_GAP_REASON, price_gap_windows

MONDAY = date(2026, 7, 6)  # a Monday, keeps weekday math obvious


class _AwaitableList:
    """Mimic a Tortoise QuerySet: awaiting it yields the row list."""

    def __init__(self, items: list) -> None:
        self._items = items

    def __await__(self):
        async def _coro():
            return self._items

        return _coro().__await__()


def _run(weekdays: list[int], overrides: list, *, horizon_days: int, pid=None):
    """Run price_gap_windows with the two model .filter() calls patched."""
    weekday_rows = [SimpleNamespace(weekday=w) for w in weekdays]
    override_rows = [SimpleNamespace(start_date=s, end_date=e) for s, e in overrides]
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
        return asyncio.run(
            price_gap_windows(
                pid or uuid4(), horizon_days=horizon_days, today=MONDAY
            )
        )


def test_no_prices_blocks_entire_horizon():
    """With no weekday prices or overrides, every day in the horizon is blocked."""
    windows = _run(weekdays=[], overrides=[], horizon_days=7)

    assert len(windows) == 1
    assert windows[0].start_date == MONDAY
    assert windows[0].end_date == MONDAY + timedelta(days=7)
    assert windows[0].reason == PRICE_GAP_REASON


def test_all_weekdays_priced_leaves_no_gaps():
    """A price on every weekday means no day is unavailable."""
    windows = _run(weekdays=list(range(7)), overrides=[], horizon_days=7)

    assert windows == []


def test_override_range_splits_gaps():
    """An override in the middle of the horizon splits the gap into two windows."""
    # Override covers Wed–Fri (today+2 .. today+4 inclusive); no weekday prices.
    override = (MONDAY + timedelta(days=2), MONDAY + timedelta(days=4))
    windows = _run(weekdays=[], overrides=[override], horizon_days=7)

    assert [(w.start_date, w.end_date) for w in windows] == [
        (MONDAY, MONDAY + timedelta(days=2)),  # Mon–Tue blocked
        (MONDAY + timedelta(days=5), MONDAY + timedelta(days=7)),  # Sat–Sun blocked
    ]


def test_window_ids_are_stable():
    """Synthetic ids are deterministic so callers can key on them."""
    pid = uuid4()
    first = _run(weekdays=[], overrides=[], horizon_days=3, pid=pid)
    second = _run(weekdays=[], overrides=[], horizon_days=3, pid=pid)

    assert first[0].id == second[0].id
