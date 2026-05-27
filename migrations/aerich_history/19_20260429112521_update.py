from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """ALTER TABLE properties RENAME COLUMN gap_premium_pct to gap_tax_pct"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """ALTER TABLE properties RENAME COLUMN gap_tax_pct to gap_premium_pct"""


MODELS_STATE = (
    "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"
    "lW23S/vt59TGXOfG8vI/o6we6A=="
)
