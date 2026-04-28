"""Integration tests for GET/PUT /properties/{id}/pricing/weekdays,
GET/POST/PATCH/DELETE /properties/{id}/pricing/overrides, and
GET /properties/{id}/pricing/resolve.

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
from tests.factories import (
    OWNER_ID,
    PROPERTY_ID,
    make_admin,
    make_user,
    make_user_without_scopes,
)
from app.scopes import PropertyScope

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WEEKDAY_RULE_ID = uuid4()
OVERRIDE_ID = uuid4()


def weekday_price_out(**overrides) -> dict:
    base = {
        "id": str(WEEKDAY_RULE_ID),
        "property_id": str(PROPERTY_ID),
        "weekday": 0,
        "price": "75.00",
    }
    return {**base, **overrides}


def override_out(**overrides) -> dict:
    base = {
        "id": str(OVERRIDE_ID),
        "property_id": str(PROPERTY_ID),
        "start_date": "2026-12-25",
        "end_date": "2026-12-25",
        "price": "150.00",
        "label": "Christmas",
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
# Weekday prices — list
# ---------------------------------------------------------------------------


def test_list_weekday_prices_public(owner_client):
    with patch("app.routers.pricing.weekday_price_crud") as mock:
        mock.list_for_property = AsyncMock(return_value=[weekday_price_out()])
        resp = owner_client.get(f"/properties/{PROPERTY_ID}/pricing/weekdays")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["weekday"] == 0
    assert data[0]["price"] == "75.00"


def test_list_weekday_prices_empty(owner_client):
    with patch("app.routers.pricing.weekday_price_crud") as mock:
        mock.list_for_property = AsyncMock(return_value=[])
        resp = owner_client.get(f"/properties/{PROPERTY_ID}/pricing/weekdays")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Weekday prices — upsert
# ---------------------------------------------------------------------------


def test_put_weekday_prices_owner(owner_client):
    payload = [{"weekday": 5, "price": "90.00"}, {"weekday": 6, "price": "90.00"}]
    with (
        patch("app.routers.pricing.assert_owns_property", new_callable=AsyncMock),
        patch("app.routers.pricing.weekday_price_crud") as mock,
    ):
        mock.upsert_all = AsyncMock(
            return_value=[
                weekday_price_out(weekday=5, price="90.00"),
                weekday_price_out(weekday=6, price="90.00"),
            ]
        )
        resp = owner_client.put(
            f"/properties/{PROPERTY_ID}/pricing/weekdays", json=payload
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_put_weekday_prices_duplicate_weekday_rejected(owner_client):
    payload = [{"weekday": 0, "price": "90.00"}, {"weekday": 0, "price": "95.00"}]
    resp = owner_client.put(
        f"/properties/{PROPERTY_ID}/pricing/weekdays", json=payload
    )
    assert resp.status_code == 422


def test_put_weekday_prices_invalid_weekday_rejected(owner_client):
    payload = [{"weekday": 7, "price": "90.00"}]
    resp = owner_client.put(
        f"/properties/{PROPERTY_ID}/pricing/weekdays", json=payload
    )
    assert resp.status_code == 422


def test_put_weekday_prices_no_schedule_scope_forbidden(client_factory=None):
    user = make_user_without_scopes(PropertyScope.SCHEDULE)
    app = FastAPI()
    app.include_router(router)
    app.state.limiter = limiter

    async def _user():
        return user

    app.dependency_overrides[get_current_user] = _user
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.put(
        f"/properties/{PROPERTY_ID}/pricing/weekdays",
        json=[{"weekday": 0, "price": "90.00"}],
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Date overrides — list
# ---------------------------------------------------------------------------


def test_list_overrides_public(owner_client):
    with patch("app.routers.pricing.date_override_crud") as mock:
        mock.list_for_property = AsyncMock(return_value=[override_out()])
        resp = owner_client.get(f"/properties/{PROPERTY_ID}/pricing/overrides")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_overrides_with_date_filter(owner_client):
    with patch("app.routers.pricing.date_override_crud") as mock:
        mock.list_for_property = AsyncMock(return_value=[])
        resp = owner_client.get(
            f"/properties/{PROPERTY_ID}/pricing/overrides",
            params={"from_date": "2026-12-01", "to_date": "2026-12-31"},
        )
    assert resp.status_code == 200
    mock.list_for_property.assert_awaited_once_with(
        PROPERTY_ID,
        date(2026, 12, 1),
        date(2026, 12, 31),
    )


# ---------------------------------------------------------------------------
# Date overrides — create
# ---------------------------------------------------------------------------


def test_create_override_owner(owner_client):
    payload = {
        "start_date": "2026-12-25",
        "end_date": "2026-12-25",
        "price": "150.00",
        "label": "Christmas",
    }
    with (
        patch("app.routers.pricing.assert_owns_property", new_callable=AsyncMock),
        patch("app.routers.pricing.date_override_crud") as mock,
    ):
        mock.create_for_property = AsyncMock(return_value=override_out())
        resp = owner_client.post(
            f"/properties/{PROPERTY_ID}/pricing/overrides", json=payload
        )
    assert resp.status_code == 201
    assert resp.json()["label"] == "Christmas"


def test_create_override_invalid_dates_rejected(owner_client):
    payload = {
        "start_date": "2026-12-26",
        "end_date": "2026-12-25",
        "price": "150.00",
    }
    resp = owner_client.post(
        f"/properties/{PROPERTY_ID}/pricing/overrides", json=payload
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Date overrides — update
# ---------------------------------------------------------------------------


def test_update_override_owner(owner_client):
    payload = {"price": "175.00"}
    with (
        patch("app.routers.pricing.assert_owns_property", new_callable=AsyncMock),
        patch("app.routers.pricing.date_override_crud") as mock,
    ):
        mock.update = AsyncMock(return_value=override_out(price="175.00"))
        resp = owner_client.patch(
            f"/properties/{PROPERTY_ID}/pricing/overrides/{OVERRIDE_ID}", json=payload
        )
    assert resp.status_code == 200
    assert resp.json()["price"] == "175.00"


def test_update_override_not_found(owner_client):
    payload = {"price": "175.00"}
    with (
        patch("app.routers.pricing.assert_owns_property", new_callable=AsyncMock),
        patch("app.routers.pricing.date_override_crud") as mock,
    ):
        mock.update = AsyncMock(return_value=None)
        resp = owner_client.patch(
            f"/properties/{PROPERTY_ID}/pricing/overrides/{OVERRIDE_ID}", json=payload
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Date overrides — delete
# ---------------------------------------------------------------------------


def test_delete_override_owner(owner_client):
    with (
        patch("app.routers.pricing.assert_owns_property", new_callable=AsyncMock),
        patch("app.routers.pricing.date_override_crud") as mock,
    ):
        mock.delete = AsyncMock(return_value=True)
        resp = owner_client.delete(
            f"/properties/{PROPERTY_ID}/pricing/overrides/{OVERRIDE_ID}"
        )
    assert resp.status_code == 204


def test_delete_override_not_found(owner_client):
    with (
        patch("app.routers.pricing.assert_owns_property", new_callable=AsyncMock),
        patch("app.routers.pricing.date_override_crud") as mock,
    ):
        mock.delete = AsyncMock(return_value=False)
        resp = owner_client.delete(
            f"/properties/{PROPERTY_ID}/pricing/overrides/{OVERRIDE_ID}"
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Resolve endpoint
# ---------------------------------------------------------------------------


def test_resolve_returns_breakdown(owner_client):
    property_mock = MagicMock()
    property_mock.price_per_night = Decimal("50.00")
    property_mock.currency = "EUR"

    nights = [
        MagicMock(date=date(2026, 6, 8), price=Decimal("50.00"), source="base", label=None),
        MagicMock(date=date(2026, 6, 9), price=Decimal("75.00"), source="weekday", label=None),
    ]

    with (
        patch("app.routers.pricing.Property") as MockProperty,
        patch("app.routers.pricing.resolve_prices_for_property", new_callable=AsyncMock, return_value=nights),
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
    assert body["nights"][0]["source"] == "base"
    assert body["nights"][1]["source"] == "weekday"


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
