"""Detail read (``PropertyCRUD.get_property``) must resolve ``city`` from the
settlement, not echo the raw nullable DB column.

The list projection (``_build_list_item``) already does this; the single-property
detail endpoint used to ``model_validate`` the ORM row directly, leaking the
legacy ``city`` field (null for EKATTE-only properties) to callers such as the
bookings-ms check-in roster. Real in-memory SQLite, same style as
``test_search_pricing_coverage.py``.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import TypeVar

from tortoise import Tortoise

from app.crud import property_crud
from app.models import Property, PropertyTranslation

# EKATTE 00014 -> "Абланица" (bg) / "Ablanitsa" (en); verified against the
# bundled settlements dataset.
EKATTE_ABLANITSA = "00014"

T = TypeVar("T")


def _with_db(coro_factory: Callable[[], Awaitable[T]]) -> T:
    async def _runner() -> T:
        await Tortoise.init(
            db_url="sqlite://:memory:", modules={"models": ["app.models"]}
        )
        await Tortoise.generate_schemas()
        try:
            return await coro_factory()
        finally:
            await Tortoise.close_connections()

    return asyncio.run(_runner())


async def _make_property(*, settlement_ekatte: str | None, city: str | None) -> uuid.UUID:
    prop = await Property.create(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        settlement_ekatte=settlement_ekatte,
        city=city,
    )
    await PropertyTranslation.create(
        id=uuid.uuid4(),
        property=prop,
        locale="bg",
        name="Хижа",
        description="Уютна хижа в планината.",
        address="ул. Тест 1",
    )
    return prop.id


def test_get_property_resolves_city_from_settlement_when_db_city_null():
    async def scenario() -> None:
        # EKATTE-only property with a null legacy city (the common new-property case).
        pid = await _make_property(settlement_ekatte=EKATTE_ABLANITSA, city=None)

        bg = await property_crud.get_property(pid)
        assert bg is not None
        assert bg.city == "Абланица"

        en = await property_crud.get_property(pid, locale="en")
        assert en is not None
        assert en.city == "Ablanitsa"

    _with_db(scenario)


def test_get_property_falls_back_to_legacy_city_when_settlement_unresolvable():
    async def scenario() -> None:
        # No settlement (or an unknown one) -> keep the legacy free-text city.
        pid = await _make_property(settlement_ekatte=None, city="Old Town")

        resp = await property_crud.get_property(pid)
        assert resp is not None
        assert resp.city == "Old Town"

    _with_db(scenario)
