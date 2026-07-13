from enum import StrEnum

from ms_core import AbstractModel as Model
from tortoise import fields
from tortoise.contrib.postgres.fields import TSVectorField


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


class PatchedTSVectorField(TSVectorField):
    """
    Patches TSVectorField to support both DB loading and validation.
    """

    # 1. Setting this as a class attribute fixes the 'NoneType' callable error.
    # 2. Using 'str' fixes the 'isinstance() arg 2 must be a type' error.
    field_type = str


class Property(Model):
    id = fields.UUIDField(primary_key=True)

    property_type = fields.CharEnumField(PropertyType, default=PropertyType.APARTMENT)
    status = fields.CharEnumField(
        PropertyStatus, default=PropertyStatus.PENDING_APPROVAL
    )

    owner_id = fields.UUIDField()

    # Tourism registry number (рег. номер на обекта) — immutable after creation
    registration_number = fields.CharField(max_length=50, null=True)

    # Location (non-translatable)
    region_code = fields.CharField(max_length=10, null=True)  # oblast code e.g. "SFO"
    settlement_ekatte = fields.CharField(
        max_length=10, null=True
    )  # EKATTE code e.g. "68134"
    # DEPRECATED as input: never set on new properties (located via
    # settlement_ekatte). Kept only as a fallback for pre-EKATTE rows. Read
    # schemas expose ``city`` as the settlement name resolved from
    # settlement_ekatte (see crud.py), falling back to this column.
    city = fields.CharField(max_length=100, null=True)
    latitude = fields.DecimalField(max_digits=9, decimal_places=6, null=True)
    longitude = fields.DecimalField(max_digits=9, decimal_places=6, null=True)

    # Price — system-owned projection of the pricing calendar, never owner input.
    # Maintained by app.services.pricing_cache on every pricing-calendar change.
    # price_from: cheapest configured nightly rate (None until pricing is set).
    # has_valid_pricing: >=1 priced day within the booking horizon; gates public
    # listing visibility.
    price_from = fields.DecimalField(max_digits=8, decimal_places=2, null=True)
    has_valid_pricing = fields.BooleanField(default=False)
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

    # Payment configuration (serialized PaymentConfig)
    payment_config = fields.JSONField(default=dict)

    # Gap filler
    enable_gap_filler = fields.BooleanField(default=False)
    gap_tax_pct = fields.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )  # -100–100 percent
    gap_last_minute_window = fields.IntField(default=7)  # days from today
    gap_adjacent_only = fields.BooleanField(default=True)  # legacy: always True

    # Meta
    rating = fields.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    total_reviews = fields.IntField(default=0)

    updated_at = fields.DatetimeField(auto_now=True)

    # Relations
    images: fields.ReverseRelation["PropertyImage"]
    unavailabilities: fields.ReverseRelation["PropertyUnavailability"]
    translations: fields.ReverseRelation["PropertyTranslation"]
    date_prices: fields.ReverseRelation["PropertyDatePrice"]

    class Meta:
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
    search_vector = PatchedTSVectorField(null=True)

    class Meta:
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

    class Meta:
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

    class Meta:
        table = "property_unavailabilities"


class PropertyDatePrice(Model):
    """One priced night. The calendar is the sole source of price and availability.

    A date with a row is bookable at ``price``; a date with no row is unpriced and
    therefore unavailable. There are no recurring weekday defaults and no
    base-price fallback.
    """

    id = fields.UUIDField(primary_key=True)
    property = fields.ForeignKeyField(
        "models.Property", related_name="date_prices", on_delete=fields.CASCADE
    )
    date = fields.DateField()
    price = fields.DecimalField(max_digits=8, decimal_places=2)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "property_date_prices"
        unique_together = (("property", "date"),)
        ordering = ["date"]
