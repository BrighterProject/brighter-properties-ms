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


def _gap_window() -> PropertyUnavailabilityResponse:
    return PropertyUnavailabilityResponse(
        id=uuid4(),
        property_id=PROPERTY_ID,
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 10),
        reason="Няма зададена цена за тази дата",
    )


def test_list_unavailabilities_excludes_price_gaps_by_default(owner_client):
    """Owner-facing listing returns only real windows, no synthetic price gaps."""
    with (
        patch("app.routers.unavail.property_unavailability_crud") as mock_crud,
        patch(
            "app.routers.unavail.price_gap_windows", new_callable=AsyncMock
        ) as mock_gaps,
    ):
        mock_crud.list_for_property = AsyncMock(return_value=[_real_window()])
        resp = owner_client.get(f"/properties/{PROPERTY_ID}/unavailabilities")

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    mock_gaps.assert_not_awaited()


def test_list_unavailabilities_includes_price_gaps_when_requested(owner_client):
    """The booking flow opts in and gets real + synthetic price-gap windows merged."""
    with (
        patch("app.routers.unavail.property_unavailability_crud") as mock_crud,
        patch(
            "app.routers.unavail.price_gap_windows", new_callable=AsyncMock
        ) as mock_gaps,
    ):
        mock_crud.list_for_property = AsyncMock(return_value=[_real_window()])
        mock_gaps.return_value = [_gap_window()]
        resp = owner_client.get(
            f"/properties/{PROPERTY_ID}/unavailabilities",
            params={"include_price_gaps": "true"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    reasons = {w["reason"] for w in body}
    assert "Няма зададена цена за тази дата" in reasons
    mock_gaps.assert_awaited_once_with(PROPERTY_ID)
