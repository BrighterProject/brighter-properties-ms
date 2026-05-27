from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE properties ADD COLUMN region_code VARCHAR(10) NULL;
        ALTER TABLE properties ADD COLUMN settlement_ekatte VARCHAR(10) NULL;
        ALTER TABLE properties ALTER COLUMN city DROP NOT NULL;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE properties DROP COLUMN region_code;
        ALTER TABLE properties DROP COLUMN settlement_ekatte;
        UPDATE properties SET city = '' WHERE city IS NULL;
        ALTER TABLE properties ALTER COLUMN city SET NOT NULL;
    """


MODELS_STATE = (
    "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"
)


MODELS_STATE = (
    "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"
)
