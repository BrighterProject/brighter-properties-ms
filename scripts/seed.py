"""
Seed script — inserts realistic Bulgarian property fixtures.
Skips if active properties already exist (use --force to override).

Usage:
    DB_URL=asyncpg://user:pass@localhost:5432/brighter uv run python scripts/seed.py
    DB_URL=... uv run python scripts/seed.py --force
"""

import asyncio
import sys
import uuid
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tortoise import Tortoise

DB_URL = __import__("os").environ.get(
    "DB_URL", "asyncpg://brighter:brighter@localhost:5432/brighter"
)

MODELS = ["app.models", "aerich.models"]

# Fixed seed owner UUID — a placeholder owner for fixture properties.
SEED_OWNER_ID = uuid.UUID("b42ebeec-727b-47a1-aec9-93e214ecf837")

FIXTURES = [
    {
        "property_type": "apartment",
        "city": "Sofia",
        "latitude": Decimal("42.697708"),
        "longitude": Decimal("23.321868"),
        "price_per_night": Decimal("85.00"),
        "max_guests": 4,
        "bedrooms": 2,
        "bathrooms": 1,
        "beds": 2,
        "rooms": [
            {
                "room_type": "bedroom",
                "count": 1,
                "beds": [{"bed_type": "double", "count": 1}],
            },
            {
                "room_type": "living_room",
                "count": 1,
                "beds": [{"bed_type": "sofa_bed", "count": 1}],
            },
            {"room_type": "bathroom", "count": 1},
            {"room_type": "kitchen", "count": 1},
        ],
        "has_parking": False,
        "amenities": ["wifi", "air_conditioning", "kitchen", "washing_machine"],
        "check_in_time": "15:00",
        "check_out_time": "11:00",
        "min_nights": 2,
        "max_nights": 30,
        "cancellation_policy": "moderate",
        "rating": Decimal("8.7"),
        "total_reviews": 42,
        "translations": [
            {
                "locale": "bg",
                "name": "Луксозен апартамент в центъра на София",
                "description": (
                    "Просторен двустаен апартамент на 5 минути от НДК.\n\n"
                    "Напълно оборудвана кухня, бързи Wi-Fi и панорамна гледка към Витоша."
                ),
                "address": "бул. Витоша 15, София 1000",
            },
            {
                "locale": "en",
                "name": "Luxury Apartment in Sofia City Center",
                "description": (
                    "Spacious 2-bedroom apartment 5 minutes from the NDK.\n\n"
                    "Fully equipped kitchen, fast Wi-Fi, and a panoramic view of Vitosha."
                ),
                "address": "15 Vitosha Blvd, Sofia 1000",
            },
        ],
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800",
                "is_thumbnail": True,
                "order": 0,
            },
            {
                "url": "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800",
                "is_thumbnail": False,
                "order": 1,
            },
        ],
    },
    {
        "property_type": "villa",
        "city": "Bansko",
        "latitude": Decimal("41.837303"),
        "longitude": Decimal("23.487750"),
        "price_per_night": Decimal("220.00"),
        "max_guests": 8,
        "bedrooms": 4,
        "bathrooms": 2,
        "beds": 5,
        "rooms": [
            {
                "room_type": "bedroom",
                "count": 4,
                "beds": [
                    {"bed_type": "double", "count": 3},
                    {"bed_type": "single", "count": 2},
                ],
            },
            {"room_type": "living_room", "count": 1},
            {"room_type": "bathroom", "count": 2},
            {"room_type": "kitchen", "count": 1},
        ],
        "has_parking": True,
        "amenities": [
            "wifi",
            "fireplace",
            "kitchen",
            "bbq",
            "mountain_view",
            "ski_storage",
        ],
        "check_in_time": "14:00",
        "check_out_time": "12:00",
        "min_nights": 3,
        "max_nights": 14,
        "cancellation_policy": "moderate",
        "rating": Decimal("9.2"),
        "total_reviews": 28,
        "translations": [
            {
                "locale": "bg",
                "name": "Ски вила с камина в Банско",
                "description": (
                    "Четири спални вила с невероятна гледка към Пирин.\n\n"
                    "Камина, напълно оборудвана кухня и паркинг.\n"
                    "На 300м от пистите."
                ),
                "address": "ул. Пирин 42, Банско 2770",
            },
            {
                "locale": "en",
                "name": "Ski Villa with Fireplace in Bansko",
                "description": (
                    "Four-bedroom villa with stunning views of Pirin mountain.\n\n"
                    "Fireplace, fully equipped kitchen, and private parking.\n"
                    "300m from the ski slopes."
                ),
                "address": "42 Pirin St, Bansko 2770",
            },
        ],
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1510798831971-661eb04b3739?w=800",
                "is_thumbnail": True,
                "order": 0,
            },
            {
                "url": "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=800",
                "is_thumbnail": False,
                "order": 1,
            },
        ],
    },
    {
        "property_type": "hotel",
        "city": "Plovdiv",
        "latitude": Decimal("42.150350"),
        "longitude": Decimal("24.750450"),
        "price_per_night": Decimal("65.00"),
        "max_guests": 2,
        "bedrooms": 1,
        "bathrooms": 1,
        "beds": 1,
        "rooms": [
            {
                "room_type": "bedroom",
                "count": 1,
                "beds": [{"bed_type": "double", "count": 1}],
            },
            {"room_type": "bathroom", "count": 1},
        ],
        "has_parking": True,
        "amenities": [
            "wifi",
            "breakfast_included",
            "air_conditioning",
            "reception_24h",
        ],
        "check_in_time": "13:00",
        "check_out_time": "12:00",
        "min_nights": 1,
        "max_nights": 30,
        "cancellation_policy": "free",
        "rating": Decimal("8.4"),
        "total_reviews": 76,
        "translations": [
            {
                "locale": "bg",
                "name": "Бутиков хотел в Стария град на Пловдив",
                "description": (
                    "Уютен бутиков хотел в сърцето на Стария град.\n\n"
                    "Включена закуска, безплатен паркинг и 24-часова рецепция.\n"
                    "На крачка от Главната улица."
                ),
                "address": "ул. Княз Церетелев 3, Пловдив 4000",
            },
            {
                "locale": "en",
                "name": "Boutique Hotel in Plovdiv Old Town",
                "description": (
                    "Cozy boutique hotel in the heart of the Old Town.\n\n"
                    "Breakfast included, free parking, and 24-hour reception.\n"
                    "Steps from the main pedestrian street."
                ),
                "address": "3 Knyaz Tseretelev St, Plovdiv 4000",
            },
        ],
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=800",
                "is_thumbnail": True,
                "order": 0,
            },
        ],
    },
    {
        "property_type": "apartment",
        "city": "Varna",
        "latitude": Decimal("43.214103"),
        "longitude": Decimal("27.914733"),
        "price_per_night": Decimal("110.00"),
        "max_guests": 6,
        "bedrooms": 3,
        "bathrooms": 2,
        "beds": 4,
        "rooms": [
            {
                "room_type": "bedroom",
                "count": 3,
                "beds": [
                    {"bed_type": "double", "count": 2},
                    {"bed_type": "single", "count": 2},
                ],
            },
            {"room_type": "living_room", "count": 1},
            {"room_type": "bathroom", "count": 2},
            {"room_type": "kitchen", "count": 1},
        ],
        "has_parking": True,
        "amenities": [
            "wifi",
            "sea_view",
            "air_conditioning",
            "kitchen",
            "balcony",
            "pool",
        ],
        "check_in_time": "15:00",
        "check_out_time": "11:00",
        "min_nights": 3,
        "max_nights": 21,
        "cancellation_policy": "strict",
        "rating": Decimal("9.0"),
        "total_reviews": 53,
        "translations": [
            {
                "locale": "bg",
                "name": "Апартамент с морска гледка — Варна Бийч",
                "description": (
                    "Просторен тристаен апартамент с директна гледка към Черно море.\n\n"
                    "Балкон, достъп до басейн и паркинг.\n"
                    "На 100м от плажа."
                ),
                "address": "к.к. Чайка, бл. 12, ет. 8, Варна 9000",
            },
            {
                "locale": "en",
                "name": "Sea-View Apartment — Varna Beach",
                "description": (
                    "Spacious 3-bedroom apartment with direct Black Sea views.\n\n"
                    "Balcony, pool access, and private parking.\n"
                    "100m from the beach."
                ),
                "address": "Chaika Resort, Block 12, Floor 8, Varna 9000",
            },
        ],
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800",
                "is_thumbnail": True,
                "order": 0,
            },
            {
                "url": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=800",
                "is_thumbnail": False,
                "order": 1,
            },
        ],
    },
    {
        "property_type": "house",
        "city": "Plovdiv",
        "latitude": Decimal("42.148150"),
        "longitude": Decimal("24.744600"),
        "price_per_night": Decimal("130.00"),
        "max_guests": 10,
        "bedrooms": 4,
        "bathrooms": 2,
        "beds": 6,
        "rooms": [
            {
                "room_type": "bedroom",
                "count": 4,
                "beds": [
                    {"bed_type": "double", "count": 2},
                    {"bed_type": "single", "count": 4},
                ],
            },
            {"room_type": "living_room", "count": 1},
            {"room_type": "bathroom", "count": 2},
            {"room_type": "kitchen", "count": 1},
        ],
        "has_parking": True,
        "amenities": [
            "wifi",
            "garden",
            "bbq",
            "kitchen",
            "washing_machine",
            "pet_friendly",
        ],
        "check_in_time": "14:00",
        "check_out_time": "12:00",
        "min_nights": 2,
        "max_nights": 30,
        "cancellation_policy": "moderate",
        "rating": Decimal("8.9"),
        "total_reviews": 34,
        "translations": [
            {
                "locale": "bg",
                "name": "Просторна къща с градина в Пловдив",
                "description": (
                    "Четири спални самостоятелна къща с голяма градина и барбекю.\n\n"
                    "Подходяща за семейни събирания и корпоративни отстъпления.\n"
                    "Домашни любимци са добре дошли."
                ),
                "address": "ул. Рожен 8, Пловдив 4000",
            },
            {
                "locale": "en",
                "name": "Spacious Garden House in Plovdiv",
                "description": (
                    "Four-bedroom standalone house with a large garden and BBQ.\n\n"
                    "Perfect for family gatherings and corporate retreats.\n"
                    "Pets are welcome."
                ),
                "address": "8 Rozhen St, Plovdiv 4000",
            },
        ],
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=800",
                "is_thumbnail": True,
                "order": 0,
            },
        ],
    },
    {
        "property_type": "apartment",
        "city": "Sofia",
        "latitude": Decimal("42.692233"),
        "longitude": Decimal("23.330833"),
        "price_per_night": Decimal("55.00"),
        "max_guests": 2,
        "bedrooms": 1,
        "bathrooms": 1,
        "beds": 1,
        "rooms": [
            {
                "room_type": "studio",
                "count": 1,
                "beds": [{"bed_type": "double", "count": 1}],
            },
            {"room_type": "bathroom", "count": 1},
        ],
        "has_parking": False,
        "amenities": ["wifi", "air_conditioning", "coffee_machine"],
        "check_in_time": "16:00",
        "check_out_time": "10:00",
        "min_nights": 1,
        "max_nights": 30,
        "cancellation_policy": "free",
        "rating": Decimal("8.2"),
        "total_reviews": 61,
        "translations": [
            {
                "locale": "bg",
                "name": "Уютно студио до Националния театър, София",
                "description": (
                    "Компактно и добре обзаведено студио на крачка от Националния театър.\n\n"
                    "Идеално за бизнес пътувания и кратки почивки.\n"
                    "Включен бърз Wi-Fi."
                ),
                "address": "ул. Раковски 101, София 1000",
            },
            {
                "locale": "en",
                "name": "Cozy Studio near National Theatre, Sofia",
                "description": (
                    "Compact and well-furnished studio steps from the National Theatre.\n\n"
                    "Ideal for business trips and short breaks.\n"
                    "Fast Wi-Fi included."
                ),
                "address": "101 Rakovski St, Sofia 1000",
            },
        ],
        "images": [
            {
                "url": "https://images.unsplash.com/photo-1536376072261-38c75010e6c9?w=800",
                "is_thumbnail": True,
                "order": 0,
            },
        ],
    },
]


async def seed(force: bool = False) -> None:
    await Tortoise.init(db_url=DB_URL, modules={"models": MODELS})

    from app.models import Property, PropertyImage, PropertyTranslation

    existing = await Property.filter(status="active").count()
    if existing > 0 and not force:
        print(
            f"[seed] {existing} active properties already exist — skipping (use --force to override)"
        )
        return

    if force and existing > 0:
        deleted = await Property.filter(owner_id=SEED_OWNER_ID).delete()
        print("[seed] Deleted existing seed properties")

    created = 0
    for fixture in FIXTURES:
        translations = fixture.pop("translations")
        images = fixture.pop("images")

        prop = await Property.create(
            id=uuid.uuid4(),
            owner_id=SEED_OWNER_ID,
            status="active",
            **fixture,
        )

        for t in translations:
            await PropertyTranslation.create(id=uuid.uuid4(), property=prop, **t)

        for img in images:
            await PropertyImage.create(id=uuid.uuid4(), property=prop, **img)

        print(f"[seed] Created: {prop.city} — {translations[0]['name']}")
        created += 1

        # Restore so the script can be re-run (list references are consumed otherwise)
        fixture["translations"] = translations
        fixture["images"] = images

    print(f"[seed] Done — {created} properties inserted.")
    await Tortoise.close_connections()


if __name__ == "__main__":
    force = "--force" in sys.argv
    asyncio.run(seed(force=force))
