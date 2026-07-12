"""Recompute the pricing cache (price_from + has_valid_pricing) for all properties.

The cache is normally refreshed on every pricing-calendar write, but
``has_valid_pricing`` depends on a rolling horizon from *today*, so a property
priced only via date overrides can drift out of the horizon purely with the
passage of time (no write to trigger a refresh). Run this nightly (e.g. a
Kubernetes CronJob) to keep the cache correct.

Usage:
    DB_URL=asyncpg://user:pass@host:5432/brighter uv run python \
        scripts/recompute_pricing_cache.py
"""

from __future__ import annotations

import asyncio

from tortoise import Tortoise

from app.settings import db_url

MODELS = ["app.models"]


async def main() -> None:
    """Refresh the pricing cache for every property and report the count."""
    from app.services.pricing_cache import recompute_all_pricing_cache

    await Tortoise.init(db_url=db_url, modules={"models": MODELS})
    try:
        count = await recompute_all_pricing_cache()
        print(f"[recompute-pricing-cache] refreshed {count} properties")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
