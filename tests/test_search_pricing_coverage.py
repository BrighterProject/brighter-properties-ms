"""A search result must be fully priced for the requested stay.

Regression test: a property with two disjoint priced ranges (e.g. 15-17 and
21-24) has no owner PropertyUnavailability row and no booking in the gap, so
the old exclude-only filter let it through for a search like 13-16 even
though nights 13-14 are unpriced and therefore unbookable.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date
from decimal import Decimal

from tortoise import Tortoise

from app.crud import property_crud
from app.models import Property, PropertyDatePrice, PropertyTranslation
from app.schemas import PropertyFilters


async def _make_property(*, priced_ranges: list[tuple[date, date]]) -> uuid.UUID:
    """Create a bookable property priced only on the given [start, end) ranges."""
    prop = await Property.create(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        has_valid_pricing=True,
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
    for start, end in priced_ranges:
        day = start
        while day < end:
            await PropertyDatePrice.create(
                id=uuid.uuid4(), property=prop, date=day, price=Decimal("50.00")
            )
            day = date.fromordinal(day.toordinal() + 1)
    return prop.id


async def _run_search(
    *, priced_ranges: list[tuple[date, date]]
) -> tuple[uuid.UUID, list]:
    await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
    await Tortoise.generate_schemas()
    try:
        property_id = await _make_property(priced_ranges=priced_ranges)
        filters = PropertyFilters(
            available_from=date(2026, 7, 13), available_to=date(2026, 7, 16)
        )
        results, _total = await property_crud.list_properties(filters)
        return property_id, results
    finally:
        await Tortoise.close_connections()


def test_disjoint_priced_ranges_excluded_from_partially_unpriced_search():
    """Property priced 15-17 and 21-24 must NOT match a search for 13-16."""
    property_id, results = asyncio.run(
        _run_search(
            priced_ranges=[
                (date(2026, 7, 15), date(2026, 7, 17)),
                (date(2026, 7, 21), date(2026, 7, 24)),
            ]
        )
    )

    assert property_id not in {r.id for r in results}


def test_fully_priced_range_included_in_search():
    """Property fully priced across the requested range does match."""
    property_id, results = asyncio.run(
        _run_search(priced_ranges=[(date(2026, 7, 13), date(2026, 7, 16))])
    )

    assert property_id in {r.id for r in results}
