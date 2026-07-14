"""Tests for the unavailabilities endpoint, incl. price-gap synthesis wiring."""

from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import can_schedule_or_admin, get_current_user
from app.limiter import limiter
from app.routers.unavail import router
from app.schemas import PropertyUnavailabilityResponse
from tests.factories import make_user

PROPERTY_ID = uuid4()


def _build_app(current_user) -> FastAPI:
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
    return TestClient(_build_app(make_user()), raise_server_exceptions=True)


def _real_window() -> PropertyUnavailabilityResponse:
    return PropertyUnavailabilityResponse(
        id=uuid4(),
        property_id=PROPERTY_ID,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 5),
        reason="Maintenance",
    )


def test_list_unavailabilities_returns_only_real_windows(owner_client):
    """Listing returns real owner-set windows only — no synthetic price gaps.

    Unpriced days are exposed separately via GET /pricing/coverage.
    """
    with patch("app.routers.unavail.property_unavailability_crud") as mock_crud:
        mock_crud.list_for_property = AsyncMock(return_value=[_real_window()])
        resp = owner_client.get(f"/properties/{PROPERTY_ID}/unavailabilities")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["reason"] == "Maintenance"
