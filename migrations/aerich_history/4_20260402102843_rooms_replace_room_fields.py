from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "properties" ADD "rooms" JSONB NOT NULL DEFAULT '{}'::json;
        ALTER TABLE "properties" DROP COLUMN "bed_info";
        ALTER TABLE "properties" DROP COLUMN "room_details";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "properties" ADD "bed_info" VARCHAR(255) NOT NULL;
        ALTER TABLE "properties" ADD "room_details" VARCHAR(255) NOT NULL;
        ALTER TABLE "properties" DROP COLUMN "rooms";"""


MODELS_STATE = (
    "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"
)
