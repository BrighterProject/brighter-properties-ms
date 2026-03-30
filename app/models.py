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


SUPPORTED_LOCALES = ("en", "bg", "ru")


class Property(Model):
    id = fields.UUIDField(primary_key=True)

    property_type = fields.CharEnumField(PropertyType, default=PropertyType.APARTMENT)
    status = fields.CharEnumField(PropertyStatus, default=PropertyStatus.PENDING_APPROVAL)

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
    room_details = fields.CharField(max_length=255)
    bed_info = fields.CharField(max_length=255)

    # Features
    has_parking = fields.BooleanField(default=False)
    amenities = fields.JSONField(default=list)  # list[str]

    # Schedule
    check_in_time = fields.TimeField(null=True)   # e.g. 14:00
    check_out_time = fields.TimeField(null=True)  # e.g. 11:00

    # Booking constraints
    min_nights = fields.IntField(default=1)
    max_nights = fields.IntField(default=30)

    # Policy
    cancellation_policy = fields.CharEnumField(
        CancellationPolicy, default=CancellationPolicy.MODERATE
    )

    # Meta
    rating = fields.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    total_reviews = fields.IntField(default=0)

    updated_at = fields.DatetimeField(auto_now=True)

    # Relations
    images: fields.ReverseRelation["PropertyImage"]
    unavailabilities: fields.ReverseRelation["PropertyUnavailability"]
    translations: fields.ReverseRelation["PropertyTranslation"]

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
    start_datetime = fields.DatetimeField()
    end_datetime = fields.DatetimeField()
    reason = fields.CharField(max_length=255, null=True)

    class Meta:  # type: ignore
        table = "property_unavailabilities"
