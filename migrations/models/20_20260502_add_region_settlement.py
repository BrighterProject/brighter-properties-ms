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
