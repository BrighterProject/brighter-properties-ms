"""Tests for the expanded (BTR-53) flat amenity taxonomy.

The backend enum stays flat — it only validates values; category grouping
lives in the frontends. These tests pin the canonical value set and confirm
the create schema accepts every value.
"""

from __future__ import annotations

from app.models import AmenityType
from app.schemas import PropertyCreate
from tests.factories import property_create_payload

# The full BTR-53 taxonomy. Existing (pre-BTR-53) values MUST remain for
# backward compatibility with stored JSON; new values are additive only.
LEGACY_AMENITIES: frozenset[str] = frozenset(
    {
        "wifi",
        "air_conditioning",
        "kitchen",
        "washing_machine",
        "fireplace",
        "bbq",
        "mountain_view",
        "ski_storage",
        "breakfast_included",
        "reception_24h",
        "sea_view",
        "balcony",
        "pool",
        "garden",
        "pet_friendly",
        "coffee_machine",
    }
)

NEW_AMENITIES: frozenset[str] = frozenset(
    {
        # Views & location
        "lake_view",
        "beachfront",
        "ski_to_door",
        "city_center",
        # Kitchen & dining
        "kitchenette",
        "dishwasher",
        "microwave",
        "oven",
        "restaurant",
        # Comfort
        "heating",
        "dryer",
        "iron",
        "tv",
        "workspace",
        # Outdoors
        "indoor_pool",
        "terrace",
        "hot_tub",
        # Family
        "crib",
        "high_chair",
        "playground",
        "board_games",
        # Wellness
        "sauna",
        "spa",
        "gym",
        "massage",
        # Services
        "airport_shuttle",
        "ev_charger",
        "luggage_storage",
        "daily_housekeeping",
        # Safety & accessibility
        "smoke_alarm",
        "fire_extinguisher",
        "first_aid_kit",
        "elevator",
        "ground_floor",
        "step_free_access",
    }
)

EXPECTED_AMENITIES: frozenset[str] = LEGACY_AMENITIES | NEW_AMENITIES


def test_legacy_amenities_preserved() -> None:
    """Every pre-BTR-53 value must survive so stored JSON stays valid."""
    values = {a.value for a in AmenityType}
    assert LEGACY_AMENITIES <= values


def test_taxonomy_matches_expected_set() -> None:
    """The enum exposes exactly the agreed taxonomy — no drift."""
    assert {a.value for a in AmenityType} == EXPECTED_AMENITIES


def test_no_duplicate_values() -> None:
    """Distinct members map to distinct string values."""
    values = [a.value for a in AmenityType]
    assert len(values) == len(set(values))


def test_create_schema_accepts_full_taxonomy() -> None:
    """PropertyCreate validates a payload carrying every amenity value."""
    payload = property_create_payload()
    payload["amenities"] = sorted(EXPECTED_AMENITIES)
    model = PropertyCreate.model_validate(payload)
    assert {a.value for a in model.amenities} == EXPECTED_AMENITIES
