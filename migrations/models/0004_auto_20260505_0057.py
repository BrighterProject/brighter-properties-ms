from tortoise import migrations
from tortoise.migrations import operations as ops
import functools
from json import dumps, loads
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0003_auto_20260504_0137')]

    initial = False

    operations = [
        ops.RunSQL(
            sql="ALTER TABLE properties ADD COLUMN IF NOT EXISTS payment_config JSONB NOT NULL DEFAULT '{}'",
            reverse_sql="ALTER TABLE properties DROP COLUMN IF EXISTS payment_config",
        ),
    ]
