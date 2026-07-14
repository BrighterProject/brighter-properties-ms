from tortoise import migrations
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [('models', '0004_auto_20260505_0057')]

    initial = False

    # price_per_night stops being a stored owner-entered field. It is replaced by
    # two system-owned projections of the pricing calendar:
    #   * price_from        — cheapest configured nightly rate (nullable)
    #   * has_valid_pricing — >=1 priced day within the booking horizon
    # RunSQL is used (rather than the auto-generated AddField) so the NOT NULL
    # has_valid_pricing column gets a DB-level default and applies cleanly to
    # populated tables. Existing rows default to FALSE and are corrected by
    # app.services.pricing_cache (on the next pricing write or the nightly
    # scripts/recompute_pricing_cache.py run).
    operations = [
        ops.RunSQL(
            'ALTER TABLE "properties" ADD COLUMN "price_from" DECIMAL(8,2);',
            reverse_sql='ALTER TABLE "properties" DROP COLUMN "price_from";',
        ),
        ops.RunSQL(
            'ALTER TABLE "properties" ADD COLUMN "has_valid_pricing" BOOL NOT NULL DEFAULT FALSE;',
            reverse_sql='ALTER TABLE "properties" DROP COLUMN "has_valid_pricing";',
        ),
        ops.RunSQL(
            'ALTER TABLE "properties" DROP COLUMN "price_per_night";',
            reverse_sql='ALTER TABLE "properties" ADD COLUMN "price_per_night" DECIMAL(8,2) NOT NULL DEFAULT 0;',
        ),
    ]
