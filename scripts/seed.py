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

MODELS = ["app.models"]

# Fixed seed owner UUID — a placeholder owner for fixture properties.
SEED_OWNER_ID = uuid.UUID("b42ebeec-727b-47a1-aec9-93e214ecf837")

# Shared tourism registry number for all seeded apartments.
SEED_APARTMENT_REGISTRATION_NUMBER = "АПТ-2024-00123"

# Default payment config for seeded properties: cash on arrival, no online deposit.
SEED_PAYMENT_CONFIG = {
    "accepted_methods": ["cash"],
    "deposit_pct": 100,
    "remaining_method": None,
}

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
                    "Напълно оборудвана кухня, бързи Wi-Fi и "
                    "панорамна гледка към Витоша."
                ),
                "address": "бул. Витоша 15, София 1000",
            },
            {
                "locale": "en",
                "name": "Luxury Apartment in Sofia City Center",
                "description": (
                    "Spacious 2-bedroom apartment 5 minutes from the NDK.\n\n"
                    "Fully equipped kitchen, fast Wi-Fi, "
                    "and a panoramic view of Vitosha."
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
                    "Просторен тристаен апартамент с директна "
                    "гледка към Черно море.\n\n"
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
                    "Компактно и добре обзаведено студио на "
                    "крачка от Националния театър.\n\n"
                    "Идеално за бизнес пътувания и кратки почивки.\n"
                    "Включен бърз Wi-Fi."
                ),
                "address": "ул. Раковски 101, София 1000",
            },
            {
                "locale": "en",
                "name": "Cozy Studio near National Theatre, Sofia",
                "description": (
                    "Compact and well-furnished studio "
                    "steps from the National Theatre.\n\n"
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


def _standard_rooms(
    bedrooms: int,
    bathrooms: int,
    *,
    doubles: int | None = None,
    singles: int = 0,
    sofa_bed: bool = False,
    studio: bool = False,
) -> list[dict]:
    """Build a standard `rooms` list for a fixture (bedroom/living/bath/kitchen)."""
    if studio:
        return [
            {
                "room_type": "studio",
                "count": 1,
                "beds": [{"bed_type": "double", "count": 1}],
            },
            {"room_type": "bathroom", "count": bathrooms},
        ]

    doubles = bedrooms if doubles is None else doubles
    beds = []
    if doubles:
        beds.append({"bed_type": "double", "count": doubles})
    if singles:
        beds.append({"bed_type": "single", "count": singles})

    living_room = {"room_type": "living_room", "count": 1}
    if sofa_bed:
        living_room["beds"] = [{"bed_type": "sofa_bed", "count": 1}]

    return [
        {"room_type": "bedroom", "count": bedrooms, "beds": beds},
        living_room,
        {"room_type": "bathroom", "count": bathrooms},
        {"room_type": "kitchen", "count": 1},
    ]


# Verified-live Unsplash photo ids (HEAD 200) distinct from the ones used above,
# cycled across the coastal fixtures below for thumbnail + gallery images.
_SEA_IMAGE_IDS = [
    "1571003123894-1f0594d2b5d9",
    "1502920917128-1aa500764cbd",
    "1507525428034-b723cf961d3e",
    "1520250497591-112f2f40a3f4",
    "1499696010180-025ef6e1a8f9",
    "1505881502353-a1986add3762",
    "1527482797697-8795b05a13fe",
    "1544551763-46a013bb70d5",
    "1502672260266-1c1ef2d93688",
    "1540541338287-41700207dee6",
    "1470770841072-f978cf4d019e",
    "1445019980597-93fa8acb246c",
    "1533760881669-80db4d7b4c15",
    "1476514525535-07fb3b4ae5f1",
    "1523987355523-c7b5b0dd90a7",
    "1512100356356-de1b84283e18",
    "1499793983690-e29da59ef1c2",
    "1580587771525-78b9dba3b914",
    "1560184897-ae75f418493e",
    "1493246507139-91e8fad9978e",
    "1449034446853-66c86144b0ad",
    "1595877244574-e90ce41ce089",
    "1615571022219-eb45cf7faa9d",
    "1519046904884-53103b34b206",
    "1494526585095-c41746248156",
    "1519085360753-af0119f7cbe7",
    "1600607687939-ce8a6c25118c",
    "1523217582562-09d0def993a6",
    "1494203484021-3c454daf695d",
    "1618221469555-7f3ad97540d6",
    "1571055107559-3e67626fa8be",
    "1584132967334-10e028bd69f7",
    "1600585154340-be6161a56a0c",
    "1613977257363-707ba9348227",
    "1520277739336-7bf67edfa768",
]


def _sea_images(pair_index: int) -> list[dict]:
    """Two-image gallery (thumbnail + one more) drawn from `_SEA_IMAGE_IDS`."""
    first = _SEA_IMAGE_IDS[(pair_index * 2) % len(_SEA_IMAGE_IDS)]
    second = _SEA_IMAGE_IDS[(pair_index * 2 + 1) % len(_SEA_IMAGE_IDS)]
    return [
        {
            "url": f"https://images.unsplash.com/photo-{first}?w=800",
            "is_thumbnail": True,
            "order": 0,
        },
        {
            "url": f"https://images.unsplash.com/photo-{second}?w=800",
            "is_thumbnail": False,
            "order": 1,
        },
    ]


# (oblast_code, ekatte, bg_address, en_address) — ekatte/oblast verified against
# processing/final_merged_settlements.json (the same registry app/regions.py reads).
_SEA_TOWNS = [
    ("VAR", "10135", "к.к. Св. Св. Константин и Елена", "St. Constantine and Helena Resort"),
    ("BGS", "07079", "ул. Александровска 45", "45 Alexandrovska St"),
    ("BGS", "67800", "ул. Аполония 12, Стар град", "12 Apolonia St, Old Town"),
    ("BGS", "51500", "ул. Митрополитска 8, Стар град", "8 Mitropolitska St, Old Town"),
    ("BGS", "98212", "к.к. Слънчев бряг, до плажа", "Sunny Beach Resort, beachfront"),
    ("VAR", "94015", "к.к. Златни пясъци", "Golden Sands Resort"),
    ("BGS", "11538", "ул. Цар Симеон 5", "5 Tsar Simeon St"),
    ("BGS", "57491", "ул. Княз Борис I 22", "22 Knyaz Boris I St"),
    ("DOB", "02508", "ул. Приморска 3", "3 Primorska St"),
    ("DOB", "35064", "ул. Добротица 14", "14 Dobrotitsa St"),
    ("BGS", "48619", "ул. Хан Аспарух 9", "9 Han Asparuh St"),
    ("BGS", "00878", "ул. Странджа 6", "6 Strandzha St"),
    ("BGS", "53045", "ул. Черно море 11", "11 Cherno More St"),
    ("VAR", "07598", "ул. Андрея Цанов 4", "4 Andrea Tsanov St"),
    ("BGS", "37023", "ул. Атлиман 2", "2 Atliman St"),
    ("BGS", "58356", "ул. Трети март 7", "7 Treti Mart St"),
    ("BGS", "81178", "ул. Панорама 1", "1 Panorama St"),
    ("DOB", "39459", "ул. Оазис 3", "3 Oazis St"),
    ("VAR", "83404", "ул. Плажна 5", "5 Plazhna St"),
    ("BGS", "62459", "ул. Граничар 2", "2 Granichar St"),
]

# (property_type, bedrooms, bathrooms, max_guests, base_price, cancellation_policy,
#  has_parking, extra_amenities, doubles, singles, sofa_bed, studio)
_SEA_ARCHETYPES = [
    ("apartment", 2, 1, 4, Decimal("95.00"), "moderate", True, ["balcony", "pool"], 2, 0, False, False),
    ("house", 3, 2, 6, Decimal("140.00"), "moderate", True, ["garden", "bbq"], 2, 2, False, False),
    ("apartment", 1, 1, 2, Decimal("60.00"), "free", False, ["balcony"], 0, 0, False, True),
    ("hotel", 1, 1, 2, Decimal("75.00"), "free", True, ["breakfast_included", "reception_24h"], 1, 0, False, False),
    ("villa", 4, 3, 8, Decimal("260.00"), "strict", True, ["pool", "bbq", "garden"], 3, 2, False, False),
    ("guesthouse", 2, 1, 5, Decimal("80.00"), "moderate", True, ["breakfast_included"], 1, 1, True, False),
    ("apartment", 3, 2, 6, Decimal("120.00"), "moderate", True, ["pool", "balcony"], 2, 2, False, False),
    ("hostel", 1, 1, 2, Decimal("45.00"), "free", False, [], 1, 0, False, True),
]


def _make_sea_fixture(index: int) -> dict:
    from app.regions import get_settlement

    oblast_code, ekatte, addr_bg, addr_en = _SEA_TOWNS[index]
    settlement = get_settlement(ekatte)
    if settlement is None:
        raise ValueError(f"Unknown EKATTE code {ekatte!r} in _SEA_TOWNS")
    city_bg = settlement["name"]
    city_en = settlement["name_en"]
    lat = Decimal(str(settlement["lat"])) if settlement["lat"] is not None else None
    lon = Decimal(str(settlement["lon"])) if settlement["lon"] is not None else None

    (
        property_type,
        bedrooms,
        bathrooms,
        max_guests,
        base_price,
        cancellation_policy,
        has_parking,
        extra_amenities,
        doubles,
        singles,
        sofa_bed,
        studio,
    ) = _SEA_ARCHETYPES[index % len(_SEA_ARCHETYPES)]

    beds_count = doubles + singles + (1 if sofa_bed else 0) or 1

    return {
        "property_type": property_type,
        "region_code": oblast_code,
        "settlement_ekatte": ekatte,
        "city": city_en,
        "latitude": lat,
        "longitude": lon,
        "price_per_night": base_price,
        "max_guests": max_guests,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "beds": beds_count,
        "rooms": _standard_rooms(
            bedrooms,
            bathrooms,
            doubles=doubles,
            singles=singles,
            sofa_bed=sofa_bed,
            studio=studio,
        ),
        "has_parking": has_parking,
        "amenities": ["wifi", "sea_view", "air_conditioning", *extra_amenities],
        "check_in_time": "15:00",
        "check_out_time": "11:00",
        "min_nights": 2,
        "max_nights": 30,
        "cancellation_policy": cancellation_policy,
        "rating": Decimal("8.5"),
        "total_reviews": 20 + index * 3,
        "translations": [
            {
                "locale": "bg",
                "name": f"Апартамент с морска гледка в {city_bg}",
                "description": (
                    f"Уютно жилище на брега на Черно море в {city_bg}.\n\n"
                    "На крачки от плажа, с изглед към морето и всичко "
                    "необходимо за спокойна почивка."
                ),
                "address": f"{addr_bg}, {city_bg}",
            },
            {
                "locale": "en",
                "name": f"Sea-View Stay in {city_en}",
                "description": (
                    f"Cozy accommodation on the Black Sea coast in {city_en}.\n\n"
                    "Steps from the beach, with sea views and everything "
                    "needed for a relaxing holiday."
                ),
                "address": f"{addr_en}, {city_en}",
            },
        ],
        "images": _sea_images(index),
    }


SEA_FIXTURES = [_make_sea_fixture(i) for i in range(len(_SEA_TOWNS))]
FIXTURES.extend(SEA_FIXTURES)

for _fixture in FIXTURES:
    if _fixture["property_type"] == "apartment":
        _fixture["registration_number"] = SEED_APARTMENT_REGISTRATION_NUMBER
    _fixture.setdefault("payment_config", dict(SEED_PAYMENT_CONFIG))


async def seed(force: bool = False) -> None:
    await Tortoise.init(db_url=DB_URL, modules={"models": MODELS})

    from app.models import Property, PropertyImage, PropertyTranslation

    existing = await Property.filter(status="active").count()
    if existing > 0 and not force:
        print(
            f"[seed] {existing} active properties already exist"
            " — skipping (use --force to override)"
        )
        return

    if force and existing > 0:
        await Property.filter(owner_id=SEED_OWNER_ID).delete()
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
