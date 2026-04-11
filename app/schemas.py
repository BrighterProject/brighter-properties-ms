from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from fastapi import Query
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.models import SUPPORTED_LOCALES, AmenityType as AmenityType


class PropertyType(StrEnum):
    APARTMENT = "apartment"
    HOUSE = "house"
    VILLA = "villa"
    HOTEL = "hotel"
    HOSTEL = "hostel"
    GUESTHOUSE = "guesthouse"
    ROOM = "room"
    OTHER = "other"


class PropertyStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    PENDING_APPROVAL = "pending_approval"


class CancellationPolicy(StrEnum):
    FREE = "free"
    MODERATE = "moderate"
    STRICT = "strict"


# ---------------------------------------------------------------------------
# Translation schemas
# ---------------------------------------------------------------------------


class TranslationBase(BaseModel):
    locale: str = Field(..., max_length=5)
    name: str = Field(..., min_length=2, max_length=255)
    description: str = Field(..., min_length=10)
    address: str = Field(..., max_length=500)
    house_rules: str | None = None

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, v: str) -> str:
        if v not in SUPPORTED_LOCALES:
            raise ValueError(f"Unsupported locale '{v}'; must be one of {SUPPORTED_LOCALES}")
        return v


class TranslationCreate(TranslationBase):
    pass


class TranslationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, min_length=10)
    address: str | None = Field(default=None, max_length=500)
    house_rules: str | None = None


class TranslationResponse(TranslationBase):
    id: UUID
    property_id: UUID

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Image schemas (unchanged)
# ---------------------------------------------------------------------------


class PropertyImageBase(BaseModel):
    url: str = Field(..., max_length=500)
    is_thumbnail: bool = False
    order: int = Field(default=0, ge=0)


class PropertyImageCreate(PropertyImageBase):
    pass


class PropertyImageUpdate(BaseModel):
    url: str | None = Field(default=None, max_length=500)
    is_thumbnail: bool | None = None
    order: int | None = Field(default=None, ge=0)


class PropertyImageResponse(PropertyImageBase):
    id: UUID
    property_id: UUID

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Unavailability schemas (unchanged)
# ---------------------------------------------------------------------------


class PropertyUnavailabilityBase(BaseModel):
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def end_after_start(self) -> PropertyUnavailabilityBase:
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class PropertyUnavailabilityCreate(PropertyUnavailabilityBase):
    pass


class PropertyUnavailabilityUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    reason: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def end_after_start(self) -> PropertyUnavailabilityUpdate:
        if (
            self.start_date
            and self.end_date
            and (self.end_date <= self.start_date)
        ):
            raise ValueError("end_date must be after start_date")
        return self


class PropertyUnavailabilityResponse(PropertyUnavailabilityBase):
    id: UUID
    property_id: UUID

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Property schemas
# ---------------------------------------------------------------------------


class BedType(StrEnum):
    SINGLE = "single"
    DOUBLE = "double"
    QUEEN = "queen"
    KING = "king"
    SOFA_BED = "sofa_bed"
    BUNK = "bunk"
    CRIB = "crib"


class RoomType(StrEnum):
    BEDROOM = "bedroom"
    LIVING_ROOM = "living_room"
    KITCHEN = "kitchen"
    BATHROOM = "bathroom"
    STUDIO = "studio"


class BedEntry(BaseModel):
    bed_type: BedType
    count: int = Field(default=1, ge=1)


class RoomEntry(BaseModel):
    room_type: RoomType
    count: int = Field(default=1, ge=1)
    beds: list[BedEntry] = Field(default_factory=list)
    area_m2: float | None = Field(default=None, ge=0)


class PropertyBase(BaseModel):
    property_type: PropertyType = PropertyType.APARTMENT

    # Location
    city: str = Field(..., max_length=100)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)

    # Price
    price_per_night: Decimal = Field(..., ge=0, decimal_places=2)
    currency: Annotated[str, Field(min_length=3, max_length=3)] = "EUR"

    # Accommodation
    max_guests: int = Field(default=1, ge=1)
    bedrooms: int = Field(default=1, ge=0)
    bathrooms: int = Field(default=1, ge=0)
    beds: int = Field(default=1, ge=0)
    rooms: list[RoomEntry] = Field(default_factory=list)

    # Features
    has_parking: bool = False
    amenities: list[AmenityType] = Field(default_factory=list)

    # Schedule
    check_in_time: time | None = None
    check_out_time: time | None = None

    # Booking constraints
    min_nights: int = Field(default=1, ge=1)
    max_nights: int = Field(default=30, ge=1)

    # Policy
    cancellation_policy: CancellationPolicy = CancellationPolicy.MODERATE

    @field_validator("currency", mode="before")
    @classmethod
    def uppercase_currency(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.upper()
        return v

    @field_serializer("check_in_time", "check_out_time")
    def serialize_time(self, t: time | None):
        if t is None:
            return None
        return t.strftime("%H:%M")

    @model_validator(mode="after")
    def min_le_max_nights(self) -> PropertyBase:
        if self.min_nights > self.max_nights:
            raise ValueError("min_nights must be <= max_nights")
        return self


class PropertyCreate(PropertyBase):
    """
    Payload for POST /properties.
    owner_id is injected from the authenticated user.
    Must include at least one translation.
    """

    translations: list[TranslationCreate] = Field(..., min_length=1)

    @field_validator("translations")
    @classmethod
    def validate_translations(cls, v: list[TranslationCreate]) -> list[TranslationCreate]:
        locales = [t.locale for t in v]
        if len(locales) != len(set(locales)):
            raise ValueError("Duplicate locales in translations")
        if "bg" not in locales:
            raise ValueError("Bulgarian (bg) translation is required")
        return v


class PropertyUpdate(BaseModel):
    """Partial update — all fields optional."""

    property_type: PropertyType | None = None

    city: str | None = Field(default=None, max_length=100)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)

    price_per_night: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    max_guests: int | None = Field(default=None, ge=1)
    bedrooms: int | None = Field(default=None, ge=0)
    bathrooms: int | None = Field(default=None, ge=0)
    beds: int | None = Field(default=None, ge=0)
    rooms: list[RoomEntry] | None = None

    has_parking: bool | None = None
    amenities: list[AmenityType] | None = None

    check_in_time: time | None = None
    check_out_time: time | None = None

    min_nights: int | None = Field(default=None, ge=1)
    max_nights: int | None = Field(default=None, ge=1)

    cancellation_policy: CancellationPolicy | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def uppercase_currency(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.upper()
        return v


class PropertyStatusUpdate(BaseModel):
    """Used by admins for PATCH /properties/{id}/status."""

    status: PropertyStatus


class PropertyResponse(PropertyBase):
    """Full property representation returned from any read endpoint."""

    id: UUID
    owner_id: UUID
    status: PropertyStatus

    rating: Decimal
    total_reviews: int

    updated_at: datetime

    # Related
    translations: list[TranslationResponse] = Field(default_factory=list)
    images: list[PropertyImageResponse] = Field(default_factory=list)
    unavailabilities: list[PropertyUnavailabilityResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PropertyListItem(BaseModel):
    """
    Lightweight projection for GET /properties (list / search).
    Returns the name in the requested locale (resolved by the CRUD layer).
    """

    id: UUID
    name: str  # resolved from translations for the requested locale
    description: str  # resolved from translations for the requested locale
    city: str
    property_type: PropertyType
    status: PropertyStatus
    price_per_night: Decimal
    currency: str
    max_guests: int
    bedrooms: int
    rooms: list[RoomEntry]
    rating: Decimal
    total_reviews: int
    thumbnail: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PropertyFilters(BaseModel):
    """Bind to a FastAPI route via Depends(PropertyFilters)."""

    city: str | None = None
    property_type: Annotated[list[PropertyType] | None, Query()] = None  # multiple types allowed
    has_parking: bool | None = None
    free_cancellation: bool | None = None
    amenities: Annotated[list[AmenityType] | None, Query()] = None  # all must be present
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    min_rating: Decimal | None = Field(default=None, ge=0, le=10)
    min_guests: int | None = Field(default=None, ge=1)
    bedrooms: int | None = Field(default=None, ge=0)
    status: PropertyStatus | None = None
    owner_id: UUID | None = None

    # Date availability filter (both must be provided together)
    available_from: date | None = None  # inclusive check-in date (YYYY-MM-DD)
    available_to: date | None = None    # exclusive check-out date (YYYY-MM-DD)

    # Pagination
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def price_range_sane(self) -> PropertyFilters:
        if (
            self.min_price is not None
            and self.max_price is not None
            and (self.min_price > self.max_price)
        ):
            raise ValueError("min_price must be <= max_price")
        return self

    @model_validator(mode="after")
    def date_range_sane(self) -> PropertyFilters:
        has_from = self.available_from is not None
        has_to = self.available_to is not None
        if has_from != has_to:
            raise ValueError("available_from and available_to must be provided together")
        if has_from and has_to and self.available_from >= self.available_to:  # type: ignore[operator]
            raise ValueError("available_from must be before available_to")
        return self
