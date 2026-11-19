"""Seed the built-in roles into the permission matrix and label existing stock history."""

from django.db import migrations

# Frozen copy of the defaults at the time of this migration (later code changes must not alter history).
ROLES = [
    ("SUPER_ADMIN", "Admin", "Master control of everything: accounts, roles, settings and maintenance.", None),
    ("DESIGNER", "Designer", "Designs the website and edits products in the Designer workspace.",
     ["site.design", "catalog.edit", "catalog.media"]),
    ("ACCOUNTANT", "Accountant", "", ["accounting.view", "accounting.edit", "accounting.export", "orders.view"]),
    ("INVENTORY_MANAGER", "Inventory manager", "",
     ["inventory.view", "inventory.adjust", "inventory.reset", "inventory.batches", "production.view", "orders.view"]),
    ("PRODUCTION_MANAGER", "Production manager", "", ["production.view", "production.update", "production.manage", "inventory.view"]),
    ("EMPLOYEE_OPS", "Operations employee", "",
     ["inventory.view", "inventory.adjust", "production.view", "production.update", "leads.view", "leads.update",
      "orders.view", "orders.update"]),
    ("EMPLOYEE_CATALOG", "Catalog & media employee", "", ["catalog.media", "catalog.edit", "inventory.view"]),
    ("WHOLESALE_MANAGER", "Wholesale manager", "",
     ["leads.view", "leads.update", "inventory.view", "orders.view", "orders.create", "orders.update"]),
    ("MARKETING", "Marketing team", "Logs field and phone orders, follows up enquiries.",
     ["orders.view", "orders.create", "leads.view", "leads.update", "analytics.view", "inventory.view"]),
    ("DISTRIBUTION", "Distribution team", "Logs orders and moves them through dispatch and delivery.",
     ["orders.view", "orders.create", "orders.update", "inventory.view", "directory.view"]),
    ("WAREHOUSE", "Warehouse worker", "Packs and dispatches orders and records stock.",
     ["orders.view", "orders.update", "inventory.view", "inventory.adjust"]),
    ("VENDOR", "Supply-chain vendor", "External supplier — sees production batches only.", ["production.view"]),
]
ALL = sorted({p for *_, perms in ROLES if perms for p in perms} | {"staff.manage", "system.maintain", "analytics.view",
                                                                     "inventory.configure", "inventory.audit", "inventory.export",
                                                                     "catalog.delete", "directory.view"})


def seed(apps, schema_editor):
    RoleDefinition = apps.get_model("ops", "RoleDefinition")
    for order, (key, label, desc, perms) in enumerate(ROLES):
        RoleDefinition.objects.update_or_create(key=key, defaults={
            "label": label, "description": desc, "permissions": ALL if perms is None else perms,
            "is_builtin": True, "order": order})

    StockMovement = apps.get_model("ops", "StockMovement")
    for m in StockMovement.objects.filter(item_label="").select_related("item__product").iterator():
        if m.item_id:
            StockMovement.objects.filter(pk=m.pk).update(item_label=f"{m.item.sku} - {m.item.product.title}"[:220])
    ProductionBatch = apps.get_model("ops", "ProductionBatch")
    for b in ProductionBatch.objects.filter(item_label="").select_related("item__product").iterator():
        if b.item_id:
            ProductionBatch.objects.filter(pk=b.pk).update(item_label=f"{b.item.sku} - {b.item.product.title}"[:220])


class Migration(migrations.Migration):
    dependencies = [("ops", "0003_roles_orders_i18n")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
