"""Integration tests for the per-date pricing router:
GET/PUT/DELETE /properties/{id}/pricing/dates,
GET /properties/{id}/pricing/resolve, and
GET /properties/{id}/pricing/coverage.

All CRUD calls are mocked — no database required.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import (
    can_schedule_or_admin,
    get_current_user,
)
from app.limiter import limiter
from app.routers.pricing import router
from app.scopes import PropertyScope
from tests.factories import (
    PROPERTY_ID,
    make_admin,
    make_user,
    make_user_without_scopes,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DATE_PRICE_ID = uuid4()


def date_price_out(**overrides) -> dict:
    base = {
        "id": str(DATE_PRICE_ID),
        "property_id": str(PROPERTY_ID),
        "date": "2026-12-25",
        "price": "150.00",
    }
    return {**base, **overrides}


# ---------------------------------------------------------------------------
# App builder
# ---------------------------------------------------------------------------


def build_pricing_app(current_user) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.limiter = limiter

    async def _user():
        return current_user

    for dep in (can_schedule_or_admin, get_current_user):
        app.dependency_overrides[dep] = _user

    return app


@pytest.fixture()
def owner_client():
    return TestClient(build_pricing_app(make_user()), raise_server_exceptions=True)


@pytest.fixture()
def admin_client():
    return TestClient(build_pricing_app(make_admin()), raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Date prices — list
# ---------------------------------------------------------------------------


def test_list_date_prices_public(owner_client):
    with patch("app.routers.pricing.date_price_crud") as mock:
        mock.list_for_property = AsyncMock(return_value=[date_price_out()])
        resp = owner_client.get(f"/properties/{PROPERTY_ID}/pricing/dates")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["date"] == "2026-12-25"
    assert data[0]["price"] == "150.00"


def test_list_date_prices_empty(owner_client):
    with patch("app.routers.pricing.date_price_crud") as mock:
        mock.list_for_property = AsyncMock(return_value=[])
        resp = owner_client.get(f"/properties/{PROPERTY_ID}/pricing/dates")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_date_prices_with_date_filter(owner_client):
    with patch("app.routers.pricing.date_price_crud") as mock:
        mock.list_for_property = AsyncMock(return_value=[])
        resp = owner_client.get(
            f"/properties/{PROPERTY_ID}/pricing/dates",
            params={"from_date": "2026-12-01", "to_date": "2026-12-31"},
        )
    assert resp.status_code == 200
    mock.list_for_property.assert_awaited_once_with(
        PROPERTY_ID,
        date(2026, 12, 1),
        date(2026, 12, 31),
    )


# ---------------------------------------------------------------------------
# Date prices — set range
# ---------------------------------------------------------------------------


def test_set_date_prices_range_owner(owner_client):
    payload = {"start_date": "2026-12-24", "end_date": "2026-12-26", "price": "150.00"}
    with (
        patch("app.routers.pricing.assert_owns_property", new_callable=AsyncMock),
        patch("app.routers.pricing.sync_pricing_cache", new_callable=AsyncMock) as sync,
        patch("app.routers.pricing.date_price_crud") as mock,
    ):
        mock.upsert_range = AsyncMock(
            return_value=[
                date_price_out(date="2026-12-24"),
                date_price_out(date="2026-12-25"),
                date_price_out(date="2026-12-26"),
            ]
        )
        resp = owner_client.put(
            f"/properties/{PROPERTY_ID}/pricing/dates", json=payload
        )
    assert resp.status_code == 200
    assert len(resp.json()) == 3
    sync.assert_awaited_once_with(PROPERTY_ID)


def test_set_date_prices_single_day(owner_client):
    payload = {"start_date": "2026-12-25", "end_date": "2026-12-25", "price": "150.00"}
    with (
        patch("app.routers.pricing.assert_owns_property", new_callable=AsyncMock),
        patch("app.routers.pricing.sync_pricing_cache", new_callable=AsyncMock) as sync,
        patch("app.routers.pricing.date_price_crud") as mock,
    ):
        mock.upsert_range = AsyncMock(return_value=[date_price_out()])
        resp = owner_client.put(
            f"/properties/{PROPERTY_ID}/pricing/dates", json=payload
        )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    sync.assert_awaited_once_with(PROPERTY_ID)


def test_set_date_prices_invalid_range_rejected(owner_client):
    payload = {"start_date": "2026-12-26", "end_date": "2026-12-25", "price": "150.00"}
    resp = owner_client.put(f"/properties/{PROPERTY_ID}/pricing/dates", json=payload)
    assert resp.status_code == 422


def test_set_date_prices_no_schedule_scope_forbidden():
    user = make_user_without_scopes(PropertyScope.SCHEDULE)
    app = FastAPI()
    app.include_router(router)
    app.state.limiter = limiter

    async def _user():
        return user

    app.dependency_overrides[get_current_user] = _user
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.put(
        f"/properties/{PROPERTY_ID}/pricing/dates",
        json={"start_date": "2026-12-25", "end_date": "2026-12-25", "price": "90.00"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Date prices — clear range
# ---------------------------------------------------------------------------


def test_clear_date_prices_owner(owner_client):
    with (
        patch("app.routers.pricing.assert_owns_property", new_callable=AsyncMock),
        patch("app.routers.pricing.sync_pricing_cache", new_callable=AsyncMock) as sync,
        patch("app.routers.pricing.date_price_crud") as mock,
    ):
        mock.delete_range = AsyncMock(return_value=3)
        resp = owner_client.delete(
            f"/properties/{PROPERTY_ID}/pricing/dates",
            params={"start_date": "2026-12-24", "end_date": "2026-12-26"},
        )
    assert resp.status_code == 204
    mock.delete_range.assert_awaited_once_with(
        PROPERTY_ID, date(2026, 12, 24), date(2026, 12, 26)
    )
    sync.assert_awaited_once_with(PROPERTY_ID)


def test_clear_date_prices_invalid_range_rejected(owner_client):
    resp = owner_client.delete(
        f"/properties/{PROPERTY_ID}/pricing/dates",
        params={"start_date": "2026-12-26", "end_date": "2026-12-24"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Resolve endpoint
# ---------------------------------------------------------------------------


def test_resolve_returns_breakdown(owner_client):
    property_mock = MagicMock()
    property_mock.currency = "EUR"

    nights = [
        MagicMock(
            date=date(2026, 6, 8), price=Decimal("50.00"), source="date", label=None
        ),
        MagicMock(
            date=date(2026, 6, 9), price=Decimal("75.00"), source="date", label=None
        ),
    ]

    with (
        patch("app.routers.pricing.Property") as MockProperty,
        patch(
            "app.routers.pricing.resolve_prices_for_property",
            new_callable=AsyncMock,
            return_value=nights,
        ),
    ):
        MockProperty.get_or_none = AsyncMock(return_value=property_mock)
        resp = owner_client.get(
            f"/properties/{PROPERTY_ID}/pricing/resolve",
            params={"start_date": "2026-06-08", "end_date": "2026-06-10"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["currency"] == "EUR"
    assert body["total"] == "125.00"
    assert len(body["nights"]) == 2
    assert body["nights"][0]["source"] == "date"
    assert body["nights"][1]["source"] == "date"


def test_resolve_returns_409_for_unpriced_nights(owner_client):
    property_mock = MagicMock()
    property_mock.currency = "EUR"

    nights = [
        MagicMock(
            date=date(2026, 6, 8), price=Decimal("75.00"), source="date", label=None
        ),
        MagicMock(
            date=date(2026, 6, 9),
            price=Decimal("0.00"),
            source="unpriced",
            label=None,
        ),
    ]

    with (
        patch("app.routers.pricing.Property") as MockProperty,
        patch(
            "app.routers.pricing.resolve_prices_for_property",
            new_callable=AsyncMock,
            return_value=nights,
        ),
    ):
        MockProperty.get_or_none = AsyncMock(return_value=property_mock)
        resp = owner_client.get(
            f"/properties/{PROPERTY_ID}/pricing/resolve",
            params={"start_date": "2026-06-08", "end_date": "2026-06-10"},
        )

    assert resp.status_code == 409
    assert resp.json()["detail"]["unpriced_dates"] == ["2026-06-09"]


def test_pricing_coverage_returns_unpriced_windows(owner_client):
    from app.schemas import UnpricedWindow

    windows = [UnpricedWindow(start_date=date(2026, 6, 8), end_date=date(2026, 6, 10))]
    with patch(
        "app.routers.pricing.unpriced_windows",
        new_callable=AsyncMock,
        return_value=windows,
    ):
        resp = owner_client.get(
            f"/properties/{PROPERTY_ID}/pricing/coverage",
            params={"start": "2026-06-08", "end": "2026-06-30"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["unpriced_windows"] == [
        {"start_date": "2026-06-08", "end_date": "2026-06-10"}
    ]


def test_pricing_coverage_invalid_range(owner_client):
    resp = owner_client.get(
        f"/properties/{PROPERTY_ID}/pricing/coverage",
        params={"start": "2026-06-30", "end": "2026-06-08"},
    )
    assert resp.status_code == 422


def test_resolve_property_not_found(owner_client):
    with patch("app.routers.pricing.Property") as MockProperty:
        MockProperty.get_or_none = AsyncMock(return_value=None)
        resp = owner_client.get(
            f"/properties/{PROPERTY_ID}/pricing/resolve",
            params={"start_date": "2026-06-08", "end_date": "2026-06-10"},
        )
    assert resp.status_code == 404


def test_resolve_invalid_date_range(owner_client):
    resp = owner_client.get(
        f"/properties/{PROPERTY_ID}/pricing/resolve",
        params={"start_date": "2026-06-10", "end_date": "2026-06-08"},
    )
    assert resp.status_code == 422


def test_resolve_missing_params(owner_client):
    resp = owner_client.get(f"/properties/{PROPERTY_ID}/pricing/resolve")
    assert resp.status_code == 422
