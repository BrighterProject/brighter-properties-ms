"""
All test-data builders in one place.
Import from here in every test file — never define dummy data inline.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.deps import CurrentUser
from app.scopes import PropertyScope

# ---------------------------------------------------------------------------
# Stable IDs — use these when a specific, repeatable UUID is needed.
# Call uuid4() inline when you need a fresh one per test.
# ---------------------------------------------------------------------------

OWNER_ID: UUID = uuid4()
OTHER_USER_ID: UUID = uuid4()
ADMIN_ID: UUID = uuid4()

PROPERTY_ID: UUID = uuid4()
IMAGE_ID: UUID = uuid4()
UNAVAIL_ID: UUID = uuid4()

NOW = datetime(2026, 6, 1, 10, 0, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=3)


# ---------------------------------------------------------------------------
# User factories
# ---------------------------------------------------------------------------


def make_user(
    user_id: UUID = OWNER_ID,
    scopes: list[str] | None = None,
    is_active: bool = True,
) -> CurrentUser:
    """Regular property owner with all owner-level scopes by default."""
    if scopes is None:
        scopes = [
            PropertyScope.READ,
            PropertyScope.ME,
            PropertyScope.WRITE,
            PropertyScope.DELETE,
            PropertyScope.IMAGES,
            PropertyScope.SCHEDULE,
        ]
    return CurrentUser(
        id=user_id,
        username=f"user_{user_id}",
        scopes=scopes,
    )


def make_admin() -> CurrentUser:
    """Admin user with all admin:properties:* scopes."""
    return CurrentUser(
        id=ADMIN_ID,
        username="admin",
        scopes=[
            PropertyScope.READ,
            "admin:scopes",
            PropertyScope.ADMIN_READ,
            PropertyScope.ADMIN_WRITE,
            PropertyScope.ADMIN_DELETE,
        ],
    )


def make_inactive_user() -> CurrentUser:
    return make_user(is_active=False)


def make_user_without_scopes(*scopes_to_remove: str) -> CurrentUser:
    """Owner with specific scopes stripped — useful for 403 tests."""
    default = set(
        [
            PropertyScope.READ,
            PropertyScope.ME,
            PropertyScope.WRITE,
            PropertyScope.DELETE,
            PropertyScope.IMAGES,
            PropertyScope.SCHEDULE,
        ]
    )
    return make_user(scopes=list({str(el) for el in default} - set(scopes_to_remove)))


# ---------------------------------------------------------------------------
# Response dict factories  (mirror what the CRUD layer returns as dicts)
# These are intentionally plain dicts, not Pydantic models, so tests can
# assert on JSON response bodies directly without re-serialising.
# ---------------------------------------------------------------------------


def property_list_item(**overrides) -> dict:
    base = dict(
        id=str(PROPERTY_ID),
        name="Test Court",
        city="Sofia",
        sport_types=["tennis"],
        status="active",
        price_per_hour="20.00",
        currency="EUR",
        capacity=4,
        is_indoor=True,
        rating="4.50",
        total_reviews=10,
        thumbnail=None,
    )
    return {**base, **overrides}


def property_response(**overrides) -> dict:
    base = dict(
        id=str(PROPERTY_ID),
        owner_id=str(OWNER_ID),
        name="Test Court",
        description="A great tennis court for everyone.",
        sport_types=["tennis"],
        status="active",
        address="123 Main St",
        city="Sofia",
        latitude=None,
        longitude=None,
        price_per_hour="20.00",
        currency="EUR",
        capacity=4,
        is_indoor=True,
        has_parking=False,
        has_changing_rooms=False,
        has_showers=False,
        has_equipment_rental=False,
        amenities=[],
        working_hours={},
        rating="4.50",
        total_reviews=10,
        total_bookings=5,
        updated_at=NOW.isoformat(),
        images=[],
        unavailabilities=[],
    )
    return {**base, **overrides}


def image_response(**overrides) -> dict:
    base = dict(
        id=str(IMAGE_ID),
        property_id=str(PROPERTY_ID),
        url="https://example.com/img.jpg",
        is_thumbnail=False,
        order=0,
    )
    return {**base, **overrides}


def unavail_response(**overrides) -> dict:
    base = dict(
        id=str(UNAVAIL_ID),
        property_id=str(PROPERTY_ID),
        start_datetime=NOW.isoformat(),
        end_datetime=LATER.isoformat(),
        reason="Maintenance",
    )
    return {**base, **overrides}


# ---------------------------------------------------------------------------
# Request payload factories  (what you POST/PATCH to the API)
# ---------------------------------------------------------------------------


def property_create_payload(**overrides) -> dict:
    base = dict(
        name="Tennis Club Sofia",
        description="A great place for tennis lovers.",
        address="1 Sports Ave",
        city="Sofia",
        price_per_hour="25.00",
        sport_types=["tennis"],
    )
    return {**base, **overrides}


def unavail_create_payload(**overrides) -> dict:
    base = dict(
        start_datetime=NOW.isoformat(),
        end_datetime=LATER.isoformat(),
        reason="Maintenance",
    )
    return {**base, **overrides}
