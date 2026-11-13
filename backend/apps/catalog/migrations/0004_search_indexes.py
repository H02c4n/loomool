from django.db import migrations


FORWARD_SQL = """
CREATE EXTENSION IF NOT EXISTS pg_trgm;

ALTER TABLE catalog_product
ADD COLUMN search_vector tsvector
GENERATED ALWAYS AS (
    setweight(to_tsvector('simple', coalesce(name, '')), 'A') ||
    setweight(to_tsvector('simple', coalesce(description, '')), 'B')
) STORED;

CREATE INDEX catalog_product_search_gin
    ON catalog_product USING GIN (search_vector);

CREATE INDEX catalog_product_name_trgm
    ON catalog_product USING GIN (name gin_trgm_ops);
"""

REVERSE_SQL = """
DROP INDEX IF EXISTS catalog_product_name_trgm;
DROP INDEX IF EXISTS catalog_product_search_gin;
ALTER TABLE catalog_product DROP COLUMN IF EXISTS search_vector;
DROP EXTENSION IF EXISTS pg_trgm;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0003_productcomponent_productrelationship_and_more"),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]
