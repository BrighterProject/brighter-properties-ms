"""
All test-data builders in one place.
Import from here in every test file — never define dummy data inline.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
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
TRANSLATION_ID: UUID = uuid4()

NOW = datetime(2026, 6, 1, 10, 0, 0, tzinfo=UTC)
UNAVAIL_START = date(2026, 6, 1)
UNAVAIL_END = date(2026, 6, 5)


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
# Translation helpers
# ---------------------------------------------------------------------------


def translation_dict(locale: str = "en", **overrides) -> dict:
    bases = {
        "en": dict(
            locale="en",
            name="Cozy Apartment",
            description="A beautiful apartment in the city centre.",
            address="123 Main St",
            house_rules=None,
        ),
        "bg": dict(
            locale="bg",
            name="Уютен апартамент",
            description="Красив апартамент в центъра на града.",
            address="ул. Главна 123",
            house_rules=None,
        ),
        "ru": dict(
            locale="ru",
            name="Уютная квартира",
            description="Красивая квартира в центре города.",
            address="ул. Главная 123",
            house_rules=None,
        ),
    }
    base = bases.get(locale, bases["en"])
    return {**base, **overrides}


def translation_response(locale: str = "en", **overrides) -> dict:
    base = {
        "id": str(TRANSLATION_ID),
        "property_id": str(PROPERTY_ID),
        **translation_dict(locale),
    }
    return {**base, **overrides}


# ---------------------------------------------------------------------------
# Response dict factories
# ---------------------------------------------------------------------------


def property_list_item(**overrides) -> dict:
    base = dict(
        id=str(PROPERTY_ID),
        name="Cozy Apartment",
        description="A cozy apartment in Sofia.",
        city="Sofia",
        property_type="apartment",
        status="active",
        price_per_night="50.00",
        currency="EUR",
        max_guests=4,
        bedrooms=2,
        rooms=[
            {"room_type": "bedroom", "count": 2, "beds": [{"bed_type": "double", "count": 2}]},
            {"room_type": "bathroom", "count": 1},
        ],
        rating="4.50",
        total_reviews=10,
        thumbnail=None,
    )
    return {**base, **overrides}


def property_response(**overrides) -> dict:
    base = dict(
        id=str(PROPERTY_ID),
        owner_id=str(OWNER_ID),
        property_type="apartment",
        status="active",
        city="Sofia",
        latitude=None,
        longitude=None,
        price_per_night="50.00",
        currency="EUR",
        max_guests=4,
        bedrooms=2,
        bathrooms=1,
        beds=2,
        rooms=[
            {"room_type": "bedroom", "count": 2, "beds": [{"bed_type": "double", "count": 2}]},
            {"room_type": "bathroom", "count": 1},
        ],
        has_parking=False,
        amenities=[],
        check_in_time="14:00",
        check_out_time="11:00",
        min_nights=1,
        max_nights=30,
        cancellation_policy="moderate",
        enable_gap_filler=False,
        gap_tax_pct="0.00",
        gap_last_minute_window=7,
        gap_adjacent_only=True,
        rating="4.50",
        total_reviews=10,
        updated_at=NOW.isoformat(),
        translations=[translation_response("bg")],
        images=[],
        unavailabilities=[],
        weekday_prices=[],
        date_price_overrides=[],
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
        start_date=UNAVAIL_START.isoformat(),
        end_date=UNAVAIL_END.isoformat(),
        reason="Maintenance",
    )
    return {**base, **overrides}


# ---------------------------------------------------------------------------
# Request payload factories
# ---------------------------------------------------------------------------


def property_create_payload(**overrides) -> dict:
    base = dict(
        city="Sofia",
        price_per_night="50.00",
        property_type="apartment",
        max_guests=4,
        bedrooms=2,
        rooms=[
            {"room_type": "bedroom", "count": 2, "beds": [{"bed_type": "double", "count": 2}]},
            {"room_type": "bathroom", "count": 1},
        ],
        translations=[translation_dict("bg")],
    )
    return {**base, **overrides}


def unavail_create_payload(**overrides) -> dict:
    base = dict(
        start_date=UNAVAIL_START.isoformat(),
        end_date=UNAVAIL_END.isoformat(),
        reason="Maintenance",
    )
    return {**base, **overrides}
