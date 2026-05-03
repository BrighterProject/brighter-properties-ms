from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "properties" ADD "enable_gap_filler" BOOL NOT NULL DEFAULT False;
        ALTER TABLE "properties" ADD "gap_premium_pct" DECIMAL(5,2) NOT NULL DEFAULT 0;
        ALTER TABLE "properties" ADD "gap_adjacent_only" BOOL NOT NULL DEFAULT True;
        ALTER TABLE "properties" ADD "gap_last_minute_window" INT NOT NULL DEFAULT 7;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "properties" DROP COLUMN "enable_gap_filler";
        ALTER TABLE "properties" DROP COLUMN "gap_premium_pct";
        ALTER TABLE "properties" DROP COLUMN "gap_adjacent_only";
        ALTER TABLE "properties" DROP COLUMN "gap_last_minute_window";"""


MODELS_STATE = (
    "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"
    "/l+GXtl2u7TfgE5tzHVuLC//A420Ikw="
)
