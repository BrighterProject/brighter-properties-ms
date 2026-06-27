from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "properties" ADD "bed_info" VARCHAR(255) NOT NULL DEFAULT 'null';
        ALTER TABLE "properties" ADD "room_details" VARCHAR(255) NOT NULL DEFAULT 'null';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "properties" DROP COLUMN "bed_info";
        ALTER TABLE "properties" DROP COLUMN "room_details";"""


MODELS_STATE = (
    "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"
    "eaKzO37/ZzzAoV5e9vWF7/B3sB5WQ="
)
