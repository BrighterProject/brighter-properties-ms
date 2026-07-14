from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from uuid import uuid4
from tortoise import fields


class Migration(migrations.Migration):
    dependencies = [("models", "0005_auto_20260711_0531")]

    initial = False

    # Pricing model rewrite: recurring weekday rules + date-range overrides are
    # replaced by a single per-date price table. The calendar is the sole source
    # of price and availability — one row = one priced night. No back-fill: the
    # old tables are dropped and existing pricing rows are discarded (re-seed in
    # dev via scripts/seed.py). Only the three operations below are authored;
    # the drift the CLI adds for price_from/has_valid_pricing/payment_config
    # comes from 0005 (and payments) using RunSQL, which the state tracker can't
    # see — those columns already exist in every real environment, so applying
    # them again would fail.
    operations = [
        ops.CreateModel(
            name="PropertyDatePrice",
            fields=[
                (
                    "id",
                    fields.UUIDField(
                        primary_key=True, default=uuid4, unique=True, db_index=True
                    ),
                ),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
                (
                    "property",
                    fields.ForeignKeyField(
                        "models.Property",
                        source_field="property_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="date_prices",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("date", fields.DateField()),
                ("price", fields.DecimalField(max_digits=8, decimal_places=2)),
                ("updated_at", fields.DatetimeField(auto_now=True, auto_now_add=False)),
            ],
            options={
                "table": "property_date_prices",
                "app": "models",
                "unique_together": (("property", "date"),),
                "pk_attr": "id",
                "table_description": "One priced night. The calendar is the sole source of price and availability.",
            },
            bases=["AbstractModel"],
        ),
        ops.DeleteModel(name="PropertyDatePriceOverride"),
        ops.DeleteModel(name="PropertyWeekdayPrice"),
    ]
