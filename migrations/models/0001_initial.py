from tortoise import migrations
from tortoise.migrations import operations as ops
import functools
from app.models import CancellationPolicy, PropertyStatus, PropertyType
from json import dumps, loads
from tortoise.fields.base import OnDelete
from uuid import uuid4
from tortoise import fields

class Migration(migrations.Migration):
    initial = True

    operations = [
        ops.CreateModel(
            name='Property',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ('property_type', fields.CharEnumField(default=PropertyType.APARTMENT, description='APARTMENT: apartment\nHOUSE: house\nVILLA: villa\nHOTEL: hotel\nHOSTEL: hostel\nGUESTHOUSE: guesthouse\nROOM: room\nOTHER: other', enum_type=PropertyType, max_length=10)),
                ('status', fields.CharEnumField(default=PropertyStatus.PENDING_APPROVAL, description='ACTIVE: active\nINACTIVE: inactive\nMAINTENANCE: maintenance\nPENDING_APPROVAL: pending_approval', enum_type=PropertyStatus, max_length=16)),
                ('owner_id', fields.UUIDField()),
                ('region_code', fields.CharField(null=True, max_length=10)),
                ('settlement_ekatte', fields.CharField(null=True, max_length=10)),
                ('city', fields.CharField(null=True, max_length=100)),
                ('latitude', fields.DecimalField(null=True, max_digits=9, decimal_places=6)),
                ('longitude', fields.DecimalField(null=True, max_digits=9, decimal_places=6)),
                ('price_per_night', fields.DecimalField(max_digits=8, decimal_places=2)),
                ('currency', fields.CharField(default='EUR', max_length=3)),
                ('max_guests', fields.IntField(default=1)),
                ('bedrooms', fields.IntField(default=1)),
                ('bathrooms', fields.IntField(default=1)),
                ('beds', fields.IntField(default=1)),
                ('rooms', fields.JSONField(default=list, encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads)),
                ('has_parking', fields.BooleanField(default=False)),
                ('amenities', fields.JSONField(default=list, encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads)),
                ('check_in_time', fields.TimeField(null=True, auto_now=False, auto_now_add=False)),
                ('check_out_time', fields.TimeField(null=True, auto_now=False, auto_now_add=False)),
                ('min_nights', fields.IntField(default=1)),
                ('max_nights', fields.IntField(default=30)),
                ('cancellation_policy', fields.CharEnumField(default=CancellationPolicy.MODERATE, description='FREE: free\nMODERATE: moderate\nSTRICT: strict', enum_type=CancellationPolicy, max_length=8)),
                ('enable_gap_filler', fields.BooleanField(default=False)),
                ('gap_tax_pct', fields.DecimalField(default=0, max_digits=5, decimal_places=2)),
                ('gap_last_minute_window', fields.IntField(default=7)),
                ('gap_adjacent_only', fields.BooleanField(default=True)),
                ('rating', fields.DecimalField(default=0.0, max_digits=3, decimal_places=2)),
                ('total_reviews', fields.IntField(default=0)),
                ('updated_at', fields.DatetimeField(auto_now=True, auto_now_add=False)),
            ],
            options={'table': 'properties', 'app': 'models', 'pk_attr': 'id'},
            bases=['AbstractModel'],
        ),
        ops.CreateModel(
            name='PropertyDatePriceOverride',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ('property', fields.ForeignKeyField('models.Property', source_field='property_id', db_constraint=True, to_field='id', related_name='date_price_overrides', on_delete=OnDelete.CASCADE)),
                ('start_date', fields.DateField()),
                ('end_date', fields.DateField()),
                ('price', fields.DecimalField(max_digits=8, decimal_places=2)),
                ('label', fields.CharField(null=True, max_length=100)),
                ('updated_at', fields.DatetimeField(auto_now=True, auto_now_add=False)),
            ],
            options={'table': 'property_date_price_overrides', 'app': 'models', 'pk_attr': 'id', 'table_description': 'Holiday/special-date price override for a date range (inclusive on both ends).'},
            bases=['AbstractModel'],
        ),
        ops.CreateModel(
            name='PropertyImage',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ('property', fields.ForeignKeyField('models.Property', source_field='property_id', db_constraint=True, to_field='id', related_name='images', on_delete=OnDelete.CASCADE)),
                ('url', fields.CharField(max_length=500)),
                ('is_thumbnail', fields.BooleanField(default=False)),
                ('order', fields.IntField(default=0)),
            ],
            options={'table': 'property_images', 'app': 'models', 'pk_attr': 'id'},
            bases=['AbstractModel'],
        ),
        ops.CreateModel(
            name='PropertyTranslation',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ('property', fields.ForeignKeyField('models.Property', source_field='property_id', db_constraint=True, to_field='id', related_name='translations', on_delete=OnDelete.CASCADE)),
                ('locale', fields.CharField(max_length=5)),
                ('name', fields.CharField(max_length=255)),
                ('description', fields.TextField(unique=False)),
                ('address', fields.CharField(max_length=500)),
                ('house_rules', fields.TextField(null=True, unique=False)),
            ],
            options={'table': 'property_translations', 'app': 'models', 'unique_together': (('property', 'locale'),), 'pk_attr': 'id'},
            bases=['AbstractModel'],
        ),
        ops.CreateModel(
            name='PropertyUnavailability',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ('property', fields.ForeignKeyField('models.Property', source_field='property_id', db_constraint=True, to_field='id', related_name='unavailabilities', on_delete=OnDelete.CASCADE)),
                ('start_date', fields.DateField()),
                ('end_date', fields.DateField()),
                ('reason', fields.CharField(null=True, max_length=255)),
            ],
            options={'table': 'property_unavailabilities', 'app': 'models', 'pk_attr': 'id', 'table_description': 'Blocked date ranges — maintenance, personal reasons, etc.'},
            bases=['AbstractModel'],
        ),
        ops.CreateModel(
            name='PropertyWeekdayPrice',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ('property', fields.ForeignKeyField('models.Property', source_field='property_id', db_constraint=True, to_field='id', related_name='weekday_prices', on_delete=OnDelete.CASCADE)),
                ('weekday', fields.IntField()),
                ('price', fields.DecimalField(max_digits=8, decimal_places=2)),
                ('updated_at', fields.DatetimeField(auto_now=True, auto_now_add=False)),
            ],
            options={'table': 'property_weekday_prices', 'app': 'models', 'unique_together': (('property', 'weekday'),), 'pk_attr': 'id', 'table_description': 'Per-weekday price override. 0=Monday, 6=Sunday (ISO weekday).'},
            bases=['AbstractModel'],
        ),
    ]
