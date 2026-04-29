from enum import StrEnum

from ms_core import AbstractModel as Model
from tortoise import fields


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


class AmenityType(StrEnum):
    WIFI = "wifi"
    AIR_CONDITIONING = "air_conditioning"
    KITCHEN = "kitchen"
    WASHING_MACHINE = "washing_machine"
    FIREPLACE = "fireplace"
    BBQ = "bbq"
    MOUNTAIN_VIEW = "mountain_view"
    SKI_STORAGE = "ski_storage"
    BREAKFAST_INCLUDED = "breakfast_included"
    RECEPTION_24H = "reception_24h"
    SEA_VIEW = "sea_view"
    BALCONY = "balcony"
    POOL = "pool"
    GARDEN = "garden"
    PET_FRIENDLY = "pet_friendly"
    COFFEE_MACHINE = "coffee_machine"


SUPPORTED_LOCALES = ("en", "bg", "ru")


class Property(Model):
    id = fields.UUIDField(primary_key=True)

    property_type = fields.CharEnumField(PropertyType, default=PropertyType.APARTMENT)
    status = fields.CharEnumField(
        PropertyStatus, default=PropertyStatus.PENDING_APPROVAL
    )

    owner_id = fields.UUIDField()

    # Location (non-translatable)
    city = fields.CharField(max_length=100)
    latitude = fields.DecimalField(max_digits=9, decimal_places=6, null=True)
    longitude = fields.DecimalField(max_digits=9, decimal_places=6, null=True)

    # Price
    price_per_night = fields.DecimalField(max_digits=8, decimal_places=2)
    currency = fields.CharField(max_length=3, default="EUR")

    # Accommodation details
    max_guests = fields.IntField(default=1)
    bedrooms = fields.IntField(default=1)
    bathrooms = fields.IntField(default=1)
    beds = fields.IntField(default=1)
    rooms = fields.JSONField(
        default=list
    )  # list[RoomEntry] — structured room/bed inventory

    # Features
    has_parking = fields.BooleanField(default=False)
    amenities = fields.JSONField(default=list)  # list[AmenityType]

    # Schedule
    check_in_time = fields.TimeField(null=True)  # e.g. 14:00
    check_out_time = fields.TimeField(null=True)  # e.g. 11:00

    # Booking constraints
    min_nights = fields.IntField(default=1)
    max_nights = fields.IntField(default=30)

    # Policy
    cancellation_policy = fields.CharEnumField(
        CancellationPolicy, default=CancellationPolicy.MODERATE
    )

    # Gap filler
    enable_gap_filler = fields.BooleanField(default=False)
    gap_premium_pct = fields.DecimalField(max_digits=5, decimal_places=2, default=0)  # 0–100 percent
    gap_last_minute_window = fields.IntField(default=7)  # days from today
    gap_adjacent_only = fields.BooleanField(default=True)  # requires bookings on both sides

    # Meta
    rating = fields.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    total_reviews = fields.IntField(default=0)

    updated_at = fields.DatetimeField(auto_now=True)

    # Relations
    images: fields.ReverseRelation["PropertyImage"]
    unavailabilities: fields.ReverseRelation["PropertyUnavailability"]
    translations: fields.ReverseRelation["PropertyTranslation"]
    weekday_prices: fields.ReverseRelation["PropertyWeekdayPrice"]
    date_price_overrides: fields.ReverseRelation["PropertyDatePriceOverride"]

    class Meta:  # type: ignore
        table = "properties"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Property({self.id}, {self.city})"

    class PydanticMeta:
        exclude = ["owner__password_hash"]


class PropertyTranslation(Model):
    id = fields.UUIDField(primary_key=True)
    property = fields.ForeignKeyField(
        "models.Property", related_name="translations", on_delete=fields.CASCADE
    )
    locale = fields.CharField(max_length=5)  # "en", "bg", "ru"

    name = fields.CharField(max_length=255)
    description = fields.TextField()
    address = fields.CharField(max_length=500)
    house_rules = fields.TextField(null=True)

    class Meta:  # type: ignore
        table = "property_translations"
        unique_together = (("property", "locale"),)
        ordering = ["locale"]


class PropertyImage(Model):
    id = fields.UUIDField(primary_key=True)
    property = fields.ForeignKeyField(
        "models.Property", related_name="images", on_delete=fields.CASCADE
    )
    url = fields.CharField(max_length=500)
    is_thumbnail = fields.BooleanField(default=False)
    order = fields.IntField(default=0)

    class Meta:  # type: ignore
        table = "property_images"
        ordering = ["order"]


class PropertyUnavailability(Model):
    """Blocked date ranges — maintenance, personal reasons, etc."""

    id = fields.UUIDField(primary_key=True)
    property = fields.ForeignKeyField(
        "models.Property", related_name="unavailabilities", on_delete=fields.CASCADE
    )
    start_date = fields.DateField()
    end_date = fields.DateField()
    reason = fields.CharField(max_length=255, null=True)

    class Meta:  # type: ignore
        table = "property_unavailabilities"


class PropertyWeekdayPrice(Model):
    """Per-weekday price override. 0=Monday, 6=Sunday (ISO weekday)."""

    id = fields.UUIDField(primary_key=True)
    property = fields.ForeignKeyField(
        "models.Property", related_name="weekday_prices", on_delete=fields.CASCADE
    )
    weekday = fields.IntField()  # 0–6
    price = fields.DecimalField(max_digits=8, decimal_places=2)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:  # type: ignore
        table = "property_weekday_prices"
        unique_together = (("property", "weekday"),)
        ordering = ["weekday"]


class PropertyDatePriceOverride(Model):
    """Holiday/special-date price override for a date range (inclusive on both ends)."""

    id = fields.UUIDField(primary_key=True)
    property = fields.ForeignKeyField(
        "models.Property", related_name="date_price_overrides", on_delete=fields.CASCADE
    )
    start_date = fields.DateField()
    end_date = fields.DateField()
    price = fields.DecimalField(max_digits=8, decimal_places=2)
    label = fields.CharField(max_length=100, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:  # type: ignore
        table = "property_date_price_overrides"
        ordering = ["start_date", "created_at"]
