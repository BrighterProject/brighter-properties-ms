"""Tests for pricing coverage (unpriced day-windows)."""

import asyncio
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.coverage import compute_unpriced_windows, unpriced_windows

MONDAY = date(2026, 7, 6)  # a Monday, keeps weekday math obvious


def _weekdays(days: list[int]) -> list[SimpleNamespace]:
    return [SimpleNamespace(weekday=w) for w in days]


def _overrides(ranges: list[tuple[date, date]]) -> list[SimpleNamespace]:
    return [SimpleNamespace(start_date=s, end_date=e) for s, e in ranges]


def _windows(weekdays, overrides, *, days: int):
    start = MONDAY
    end = MONDAY + timedelta(days=days)
    result = compute_unpriced_windows(
        _weekdays(weekdays), _overrides(overrides), start=start, end=end
    )
    return [(w.start_date, w.end_date) for w in result]


# ---------------------------------------------------------------------------
# compute_unpriced_windows (pure)
# ---------------------------------------------------------------------------


def test_no_prices_blocks_entire_range():
    assert _windows([], [], days=7) == [(MONDAY, MONDAY + timedelta(days=7))]


def test_all_weekdays_priced_leaves_no_gaps():
    assert _windows(list(range(7)), [], days=7) == []


def test_override_range_splits_gaps():
    # Override covers Wed–Fri (today+2 .. today+4 inclusive); no weekday prices.
    override = (MONDAY + timedelta(days=2), MONDAY + timedelta(days=4))
    assert _windows([], [override], days=7) == [
        (MONDAY, MONDAY + timedelta(days=2)),  # Mon–Tue unpriced
        (MONDAY + timedelta(days=5), MONDAY + timedelta(days=7)),  # Sat–Sun unpriced
    ]


def test_end_exclusive():
    # Single day range -> one window covering exactly that day.
    result = compute_unpriced_windows(
        [], [], start=MONDAY, end=MONDAY + timedelta(days=1)
    )
    assert [(w.start_date, w.end_date) for w in result] == [
        (MONDAY, MONDAY + timedelta(days=1))
    ]


def test_weekday_gap_between_two_priced_runs():
    # Price Mon(0) and Wed(2); Tue(1) is unpriced in the middle.
    assert _windows([0, 2], [], days=3) == [
        (MONDAY + timedelta(days=1), MONDAY + timedelta(days=2))
    ]


# ---------------------------------------------------------------------------
# unpriced_windows (DB-backed, mocked)
# ---------------------------------------------------------------------------


class _AwaitableList:
    def __init__(self, items: list) -> None:
        self._items = items

    def __await__(self):
        async def _coro():
            return self._items

        return _coro().__await__()


def test_unpriced_windows_loads_and_computes():
    with (
        patch(
            "app.models.PropertyWeekdayPrice.filter",
            MagicMock(return_value=_AwaitableList([])),
        ),
        patch(
            "app.models.PropertyDatePriceOverride.filter",
            MagicMock(return_value=_AwaitableList([])),
        ),
    ):
        result = asyncio.run(
            unpriced_windows(
                uuid4(), start=MONDAY, end=MONDAY + timedelta(days=3), today=MONDAY
            )
        )
    assert [(w.start_date, w.end_date) for w in result] == [
        (MONDAY, MONDAY + timedelta(days=3))
    ]
