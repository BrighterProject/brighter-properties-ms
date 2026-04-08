from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "property_unavailabilities" ADD "start_date" DATE NOT NULL DEFAULT '2000-01-01';
        ALTER TABLE "property_unavailabilities" ADD "end_date" DATE NOT NULL DEFAULT '2000-01-01';
        ALTER TABLE "property_unavailabilities" DROP COLUMN "start_datetime";
        ALTER TABLE "property_unavailabilities" DROP COLUMN "end_datetime";
        ALTER TABLE "property_unavailabilities" ALTER COLUMN "start_date" DROP DEFAULT;
        ALTER TABLE "property_unavailabilities" ALTER COLUMN "end_date" DROP DEFAULT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "property_unavailabilities" ADD "start_datetime" TIMESTAMPTZ NOT NULL DEFAULT NOW();
        ALTER TABLE "property_unavailabilities" ADD "end_datetime" TIMESTAMPTZ NOT NULL DEFAULT NOW();
        ALTER TABLE "property_unavailabilities" DROP COLUMN "start_date";
        ALTER TABLE "property_unavailabilities" DROP COLUMN "end_date";
        ALTER TABLE "property_unavailabilities" ALTER COLUMN "start_datetime" DROP DEFAULT;
        ALTER TABLE "property_unavailabilities" ALTER COLUMN "end_datetime" DROP DEFAULT;"""


MODELS_STATE = (
    "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"
    "qu"
)
