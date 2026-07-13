"""Listing filters v2 — order_by, pre-pagination total, honest stay-price.

Real in-memory SQLite exercises of ``PropertyCRUD.list_properties`` (the same
style as ``test_search_pricing_coverage.py``). ``list_properties`` now returns
``(items, total)`` where ``total`` is the pre-pagination match count.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from decimal import Decimal

from tortoise import Tortoise

from app.crud import property_crud
from app.models import Property, PropertyDatePrice, PropertyTranslation
from app.schemas import PropertyFilters

SEARCH_FROM = date(2026, 7, 13)
SEARCH_TO = date(2026, 7, 16)  # 3 nights


async def _make_prop(
    *,
    owner_id: uuid.UUID | None = None,
    price_from: Decimal | None,
    rating: Decimal = Decimal("0.0"),
    total_reviews: int = 0,
    has_valid_pricing: bool = True,
    nightly: Decimal | None = None,
    priced_range: tuple[date, date] | None = None,
) -> uuid.UUID:
    """Create a property. ``nightly``+``priced_range`` seed the pricing calendar."""
    prop = await Property.create(
        id=uuid.uuid4(),
        owner_id=owner_id or uuid.uuid4(),
        price_from=price_from,
        rating=rating,
        total_reviews=total_reviews,
        has_valid_pricing=has_valid_pricing,
        min_nights=1,
        max_nights=30,
    )
    await PropertyTranslation.create(
        id=uuid.uuid4(),
        property=prop,
        locale="bg",
        name="Test",
        description="Test",
        address="Test",
    )
    if nightly is not None and priced_range is not None:
        day, end = priced_range
        while day < end:
            await PropertyDatePrice.create(
                id=uuid.uuid4(), property=prop, date=day, price=nightly
            )
            day += timedelta(days=1)
    return prop.id


def _run(coro_factory: Callable[[], Awaitable]):
    async def _wrapped():
        await Tortoise.init(
            db_url="sqlite://:memory:", modules={"models": ["app.models"]}
        )
        await Tortoise.generate_schemas()
        try:
            return await coro_factory()
        finally:
            await Tortoise.close_connections()

    return asyncio.run(_wrapped())


# ---------------------------------------------------------------------------
# Total count + pagination (no dates)
# ---------------------------------------------------------------------------


def test_total_is_prepagination_count_under_pagination():
    async def scenario():
        for i in range(5):
            await _make_prop(price_from=Decimal(f"{10 * (i + 1)}.00"))
        items, total = await property_crud.list_properties(
            PropertyFilters(page=1, page_size=2)
        )
        return items, total

    items, total = _run(scenario)
    assert total == 5
    assert len(items) == 2


def test_total_reflects_filters_not_just_page():
    async def scenario():
        await _make_prop(price_from=Decimal("10.00"))
        await _make_prop(price_from=Decimal("20.00"))
        await _make_prop(price_from=Decimal("500.00"))
        # max_price excludes the 500 one — total must be 2, not 3.
        items, total = await property_crud.list_properties(
            PropertyFilters(max_price=Decimal("100"), page_size=20)
        )
        return items, total

    items, total = _run(scenario)
    assert total == 2
    assert len(items) == 2


# ---------------------------------------------------------------------------
# order_by (no dates) — sorts on price_from / rating
# ---------------------------------------------------------------------------


def test_order_by_price_asc_no_dates():
    async def scenario():
        await _make_prop(price_from=Decimal("100.00"))
        await _make_prop(price_from=Decimal("50.00"))
        await _make_prop(price_from=Decimal("150.00"))
        items, _ = await property_crud.list_properties(
            PropertyFilters(order_by="price_asc", page_size=20)
        )
        return [p.price_from for p in items]

    prices = _run(scenario)
    assert prices == [Decimal("50.00"), Decimal("100.00"), Decimal("150.00")]


def test_order_by_price_desc_no_dates():
    async def scenario():
        await _make_prop(price_from=Decimal("100.00"))
        await _make_prop(price_from=Decimal("50.00"))
        await _make_prop(price_from=Decimal("150.00"))
        items, _ = await property_crud.list_properties(
            PropertyFilters(order_by="price_desc", page_size=20)
        )
        return [p.price_from for p in items]

    prices = _run(scenario)
    assert prices == [Decimal("150.00"), Decimal("100.00"), Decimal("50.00")]


def test_order_by_rating_desc_no_dates():
    async def scenario():
        await _make_prop(price_from=Decimal("10.00"), rating=Decimal("3.0"))
        await _make_prop(price_from=Decimal("10.00"), rating=Decimal("5.0"))
        await _make_prop(price_from=Decimal("10.00"), rating=Decimal("1.0"))
        items, _ = await property_crud.list_properties(
            PropertyFilters(order_by="rating_desc", page_size=20)
        )
        return [p.rating for p in items]

    ratings = _run(scenario)
    assert ratings == [Decimal("5.0"), Decimal("3.0"), Decimal("1.0")]


def test_order_by_price_asc_nulls_last():
    """Owner-scoped listing: an unpriced draft (price_from=None) sorts last."""
    owner = uuid.uuid4()

    async def scenario():
        await _make_prop(owner_id=owner, price_from=Decimal("80.00"))
        null_id = await _make_prop(
            owner_id=owner, price_from=None, has_valid_pricing=False
        )
        await _make_prop(owner_id=owner, price_from=Decimal("30.00"))
        items, _ = await property_crud.list_properties(
            PropertyFilters(owner_id=owner, order_by="price_asc", page_size=20)
        )
        return [p.price_from for p in items], null_id, items[-1].id

    prices, null_id, last_id = _run(scenario)
    assert prices[:2] == [Decimal("30.00"), Decimal("80.00")]
    assert last_id == null_id


# ---------------------------------------------------------------------------
# Honest stay-price filtering & sorting (with dates)
# ---------------------------------------------------------------------------


def test_stay_price_filter_uses_calendar_not_price_from():
    """max_price with dates filters on the stay's avg nightly rate, not price_from."""

    async def scenario():
        # price_from deliberately below the filter, but the stay's real nightly
        # rate (200) is above it — must be excluded.
        expensive = await _make_prop(
            price_from=Decimal("50.00"),
            nightly=Decimal("200.00"),
            priced_range=(SEARCH_FROM, SEARCH_TO),
        )
        cheap = await _make_prop(
            price_from=Decimal("50.00"),
            nightly=Decimal("50.00"),
            priced_range=(SEARCH_FROM, SEARCH_TO),
        )
        items, total = await property_crud.list_properties(
            PropertyFilters(
                available_from=SEARCH_FROM,
                available_to=SEARCH_TO,
                max_price=Decimal("100"),
                page_size=20,
            )
        )
        return {p.id for p in items}, total, expensive, cheap

    ids, total, expensive, cheap = _run(scenario)
    assert ids == {cheap}
    assert expensive not in ids
    assert total == 1


def test_stay_total_annotated_from_calendar():
    async def scenario():
        await _make_prop(
            price_from=Decimal("50.00"),
            nightly=Decimal("70.00"),
            priced_range=(SEARCH_FROM, SEARCH_TO),
        )
        items, _ = await property_crud.list_properties(
            PropertyFilters(
                available_from=SEARCH_FROM, available_to=SEARCH_TO, page_size=20
            )
        )
        return items[0]

    item = _run(scenario)
    assert item.stay_nights == 3
    assert item.stay_total == Decimal("210.00")  # 70 * 3


def test_order_by_price_asc_with_dates_uses_stay_rate():
    async def scenario():
        await _make_prop(
            price_from=Decimal("999.00"),
            nightly=Decimal("200.00"),
            priced_range=(SEARCH_FROM, SEARCH_TO),
        )
        await _make_prop(
            price_from=Decimal("999.00"),
            nightly=Decimal("50.00"),
            priced_range=(SEARCH_FROM, SEARCH_TO),
        )
        await _make_prop(
            price_from=Decimal("999.00"),
            nightly=Decimal("100.00"),
            priced_range=(SEARCH_FROM, SEARCH_TO),
        )
        items, _ = await property_crud.list_properties(
            PropertyFilters(
                available_from=SEARCH_FROM,
                available_to=SEARCH_TO,
                order_by="price_asc",
                page_size=20,
            )
        )
        return [p.stay_total for p in items]

    totals = _run(scenario)
    assert totals == [Decimal("150.00"), Decimal("300.00"), Decimal("600.00")]


def test_partially_priced_not_resurrected_by_price_filter():
    """A stay with an unpriced night stays excluded even when price filters pass."""

    async def scenario():
        # priced only 15-17, so a 13-16 search has unpriced nights 13,14.
        await _make_prop(
            price_from=Decimal("50.00"),
            nightly=Decimal("50.00"),
            priced_range=(date(2026, 7, 15), date(2026, 7, 17)),
        )
        items, total = await property_crud.list_properties(
            PropertyFilters(
                available_from=SEARCH_FROM,
                available_to=SEARCH_TO,
                min_price=Decimal("0"),
                max_price=Decimal("1000"),
                page_size=20,
            )
        )
        return items, total

    items, total = _run(scenario)
    assert items == []
    assert total == 0


# ---------------------------------------------------------------------------
# Regression — no-dates price filter still on price_from
# ---------------------------------------------------------------------------


def test_no_dates_price_filter_on_price_from_unchanged():
    async def scenario():
        await _make_prop(price_from=Decimal("50.00"))
        await _make_prop(price_from=Decimal("150.00"))
        items, total = await property_crud.list_properties(
            PropertyFilters(max_price=Decimal("100"), page_size=20)
        )
        return [p.price_from for p in items], total

    prices, total = _run(scenario)
    assert prices == [Decimal("50.00")]
    assert total == 1
