from tortoise import migrations
from tortoise.contrib.postgres.fields import TSVectorField
from tortoise.migrations import operations as ops

_TRIGGER_UP = """
CREATE OR REPLACE FUNCTION _pt_search_vector_update()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    pg_cfg TEXT;
BEGIN
    pg_cfg := CASE NEW.locale
        WHEN 'en' THEN 'english'
        WHEN 'ru' THEN 'russian'
        WHEN 'bg' THEN 'bulgarian'
        ELSE 'simple'
    END;
    NEW.search_vector :=
        SETWEIGHT(TO_TSVECTOR(pg_cfg::regconfig, COALESCE(NEW.name, '')), 'A') ||
        SETWEIGHT(TO_TSVECTOR(pg_cfg::regconfig, COALESCE(NEW.description, '')), 'B') ||
        SETWEIGHT(TO_TSVECTOR(pg_cfg::regconfig, COALESCE(NEW.address, '')), 'C');
    RETURN NEW;
END;
$$;

CREATE TRIGGER trig_pt_search_vector
    BEFORE INSERT OR UPDATE ON property_translations
    FOR EACH ROW EXECUTE FUNCTION _pt_search_vector_update();

UPDATE property_translations
SET search_vector =
    SETWEIGHT(TO_TSVECTOR(
        (CASE locale WHEN 'en' THEN 'english' WHEN 'ru' THEN 'russian' WHEN 'bg' THEN 'bulgarian' ELSE 'simple' END)::regconfig,
        COALESCE(name, '')), 'A') ||
    SETWEIGHT(TO_TSVECTOR(
        (CASE locale WHEN 'en' THEN 'english' WHEN 'ru' THEN 'russian' WHEN 'bg' THEN 'bulgarian' ELSE 'simple' END)::regconfig,
        COALESCE(description, '')), 'B') ||
    SETWEIGHT(TO_TSVECTOR(
        (CASE locale WHEN 'en' THEN 'english' WHEN 'ru' THEN 'russian' WHEN 'bg' THEN 'bulgarian' ELSE 'simple' END)::regconfig,
        COALESCE(address, '')), 'C');

CREATE INDEX idx_pt_search_vector ON property_translations USING GIN (search_vector);
"""

_TRIGGER_DOWN = """
DROP INDEX IF EXISTS idx_pt_search_vector;
DROP TRIGGER IF EXISTS trig_pt_search_vector ON property_translations;
DROP FUNCTION IF EXISTS _pt_search_vector_update();
"""


class Migration(migrations.Migration):
    dependencies = [("models", "0001_initial")]

    initial = False

    operations = [
        ops.AddField(
            model_name="PropertyTranslation",
            name="search_vector",
            field=TSVectorField(null=True, source_fields=(), stored=False),
        ),
        ops.RunSQL(_TRIGGER_UP, reverse_sql=_TRIGGER_DOWN),
    ]
