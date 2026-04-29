"""Tests for Smart Gap Filler fields on Property model and schema."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.schemas import PropertyResponse

from .factories import (
    OWNER_ID,
    PROPERTY_ID,
    make_user,
    property_create_payload,
    property_response,
)

CRUD_PATH = "app.routers.property.property_crud"
TR_CRUD_PATH = "app.routers.property.property_translation_crud"
IMG_CRUD_PATH = "app.routers.property.property_image_crud"


class TestGapFillerDefaults:
    def test_create_without_gap_filler_fields_uses_defaults(self, owner_client):
        """Creating a property without gap filler fields should return defaults."""
        payload = property_create_payload()
        created = PropertyResponse(
            **property_response(
                enable_gap_filler=False,
                gap_premium_pct="0.00",
                gap_last_minute_window=7,
                gap_adjacent_only=True,
            )
        )
        with (
            patch(CRUD_PATH) as mock_crud,
            patch(TR_CRUD_PATH) as mock_tr,
            patch(IMG_CRUD_PATH) as mock_img,
        ):
            mock_crud.create_property = AsyncMock(return_value=created)
            mock_crud.get_property = AsyncMock(return_value=created)
            mock_tr.create_for_property = AsyncMock()
            mock_img.create_for_property = AsyncMock()
            resp = owner_client.post("/properties", json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert data["enable_gap_filler"] is False
        assert data["gap_last_minute_window"] == 7
        assert data["gap_adjacent_only"] is True

    def test_create_with_gap_filler_enabled_returns_correct_values(self, owner_client):
        """Creating a property with gap filler enabled should return those values."""
        payload = property_create_payload(
            enable_gap_filler=True,
            gap_premium_pct="15.00",
            gap_last_minute_window=14,
            gap_adjacent_only=False,
        )
        created = PropertyResponse(
            **property_response(
                enable_gap_filler=True,
                gap_premium_pct="15.00",
                gap_last_minute_window=14,
                gap_adjacent_only=False,
            )
        )
        with (
            patch(CRUD_PATH) as mock_crud,
            patch(TR_CRUD_PATH) as mock_tr,
            patch(IMG_CRUD_PATH) as mock_img,
        ):
            mock_crud.create_property = AsyncMock(return_value=created)
            mock_crud.get_property = AsyncMock(return_value=created)
            mock_tr.create_for_property = AsyncMock()
            mock_img.create_for_property = AsyncMock()
            resp = owner_client.post("/properties", json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert data["enable_gap_filler"] is True
        assert float(data["gap_premium_pct"]) == 15.00
        assert data["gap_last_minute_window"] == 14
        assert data["gap_adjacent_only"] is False
