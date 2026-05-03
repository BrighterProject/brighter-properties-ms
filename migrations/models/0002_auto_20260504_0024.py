from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.contrib.postgres.fields import TSVectorField

class Migration(migrations.Migration):
    dependencies = [('models', '0001_initial')]

    initial = False

    operations = [
        ops.AddField(
            model_name='PropertyTranslation',
            name='search_vector',
            field=TSVectorField(null=True, source_fields=(), stored=False),
        ),
    ]
