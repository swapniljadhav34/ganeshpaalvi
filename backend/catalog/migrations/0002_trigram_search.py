"""
Fuzzy search indexes (PostgreSQL only).

Enables the pg_trgm extension and adds GIN trigram indexes on product title & tags,
so search stays instant — and forgiving of typos — at 50,000+ products.
On SQLite (local development) this migration does nothing.
"""

from django.db import migrations

SQL = [
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    'CREATE INDEX IF NOT EXISTS product_title_trgm ON catalog_product USING gin (UPPER("title"::text) gin_trgm_ops)',
    'CREATE INDEX IF NOT EXISTS product_tags_trgm ON catalog_product USING gin (UPPER("tags"::text) gin_trgm_ops)',
    'CREATE INDEX IF NOT EXISTS product_title_trgm_raw ON catalog_product USING gin ("title" gin_trgm_ops)',
]
REVERSE = [
    "DROP INDEX IF EXISTS product_title_trgm",
    "DROP INDEX IF EXISTS product_tags_trgm",
    "DROP INDEX IF EXISTS product_title_trgm_raw",
]


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        for stmt in SQL:
            schema_editor.execute(stmt)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        for stmt in REVERSE:
            schema_editor.execute(stmt)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]
    operations = [migrations.RunPython(forwards, backwards)]
