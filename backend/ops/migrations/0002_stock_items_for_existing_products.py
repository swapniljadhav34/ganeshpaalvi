"""Give every existing product a stock item (starting at 0 — the website's stock labels are not touched)."""

from django.db import migrations


def create_items(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    InventoryItem = apps.get_model("ops", "InventoryItem")
    Settings = apps.get_model("ops", "InventorySettings")
    cfg, _ = Settings.objects.get_or_create(pk=1)
    have = set(InventoryItem.objects.filter(variant__isnull=True).values_list("product_id", flat=True))
    InventoryItem.objects.bulk_create([
        InventoryItem(product_id=pk, sku=sku, low_stock_threshold=cfg.default_low_stock_threshold, reorder_point=cfg.default_reorder_point)
        for pk, sku in Product.objects.values_list("pk", "sku") if pk not in have
    ])


class Migration(migrations.Migration):
    dependencies = [("ops", "0001_initial"), ("catalog", "0003_product_hero_3d_order_product_is_hero_3d_featured_and_more")]
    operations = [migrations.RunPython(create_items, migrations.RunPython.noop)]
