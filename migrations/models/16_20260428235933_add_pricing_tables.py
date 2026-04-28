from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "properties" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "property_type" VARCHAR(10) NOT NULL DEFAULT 'apartment',
    "status" VARCHAR(16) NOT NULL DEFAULT 'pending_approval',
    "owner_id" UUID NOT NULL,
    "city" VARCHAR(100) NOT NULL,
    "latitude" DECIMAL(9,6),
    "longitude" DECIMAL(9,6),
    "price_per_night" DECIMAL(8,2) NOT NULL,
    "currency" VARCHAR(3) NOT NULL DEFAULT 'EUR',
    "max_guests" INT NOT NULL DEFAULT 1,
    "bedrooms" INT NOT NULL DEFAULT 1,
    "bathrooms" INT NOT NULL DEFAULT 1,
    "beds" INT NOT NULL DEFAULT 1,
    "rooms" JSONB NOT NULL,
    "has_parking" BOOL NOT NULL DEFAULT False,
    "amenities" JSONB NOT NULL,
    "check_in_time" TIMETZ,
    "check_out_time" TIMETZ,
    "min_nights" INT NOT NULL DEFAULT 1,
    "max_nights" INT NOT NULL DEFAULT 30,
    "cancellation_policy" VARCHAR(8) NOT NULL DEFAULT 'moderate',
    "rating" DECIMAL(3,2) NOT NULL DEFAULT 0,
    "total_reviews" INT NOT NULL DEFAULT 0,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON COLUMN "properties"."property_type" IS 'APARTMENT: apartment\nHOUSE: house\nVILLA: villa\nHOTEL: hotel\nHOSTEL: hostel\nGUESTHOUSE: guesthouse\nROOM: room\nOTHER: other';
COMMENT ON COLUMN "properties"."status" IS 'ACTIVE: active\nINACTIVE: inactive\nMAINTENANCE: maintenance\nPENDING_APPROVAL: pending_approval';
COMMENT ON COLUMN "properties"."cancellation_policy" IS 'FREE: free\nMODERATE: moderate\nSTRICT: strict';
        CREATE TABLE IF NOT EXISTS "property_date_price_overrides" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "start_date" DATE NOT NULL,
    "end_date" DATE NOT NULL,
    "price" DECIMAL(8,2) NOT NULL,
    "label" VARCHAR(100),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "property_id" UUID NOT NULL REFERENCES "properties" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "property_date_price_overrides" IS 'Holiday/special-date price override for a date range (inclusive on both ends).';
        CREATE TABLE IF NOT EXISTS "property_images" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "url" VARCHAR(500) NOT NULL,
    "is_thumbnail" BOOL NOT NULL DEFAULT False,
    "order" INT NOT NULL DEFAULT 0,
    "property_id" UUID NOT NULL REFERENCES "properties" ("id") ON DELETE CASCADE
);
        CREATE TABLE IF NOT EXISTS "property_translations" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "locale" VARCHAR(5) NOT NULL,
    "name" VARCHAR(255) NOT NULL,
    "description" TEXT NOT NULL,
    "address" VARCHAR(500) NOT NULL,
    "house_rules" TEXT,
    "property_id" UUID NOT NULL REFERENCES "properties" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_property_tr_propert_ae8b43" UNIQUE ("property_id", "locale")
);
        CREATE TABLE IF NOT EXISTS "property_unavailabilities" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "start_date" DATE NOT NULL,
    "end_date" DATE NOT NULL,
    "reason" VARCHAR(255),
    "property_id" UUID NOT NULL REFERENCES "properties" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "property_unavailabilities" IS 'Blocked date ranges — maintenance, personal reasons, etc.';
        CREATE TABLE IF NOT EXISTS "property_weekday_prices" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "weekday" INT NOT NULL,
    "price" DECIMAL(8,2) NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "property_id" UUID NOT NULL REFERENCES "properties" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_property_we_propert_aded3b" UNIQUE ("property_id", "weekday")
);
COMMENT ON TABLE "property_weekday_prices" IS 'Per-weekday price override. 0=Monday, 6=Sunday (ISO weekday).';
"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "property_weekday_prices";
        DROP TABLE IF EXISTS "properties";
        DROP TABLE IF EXISTS "property_images";
        DROP TABLE IF EXISTS "property_translations";
        DROP TABLE IF EXISTS "property_unavailabilities";
        DROP TABLE IF EXISTS "property_date_price_overrides";"""


MODELS_STATE = (
    "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"
)
