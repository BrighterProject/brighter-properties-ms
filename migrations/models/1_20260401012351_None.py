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
    "start_datetime" TIMESTAMPTZ NOT NULL,
    "end_datetime" TIMESTAMPTZ NOT NULL,
    "reason" VARCHAR(255),
    "property_id" UUID NOT NULL REFERENCES "properties" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "property_unavailabilities" IS 'Blocked date ranges — maintenance, personal reasons, etc.';
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
)
