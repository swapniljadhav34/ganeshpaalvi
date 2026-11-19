"""Every product automatically gets a stock item; its SKU follows the product's SKU."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from catalog.models import Product

from .models import InventoryItem


@receiver(post_save, sender=Product)
def product_stock_item(sender, instance, created, raw=False, **kwargs):
    if raw:  # loading fixtures
        return
    from .inventory import ensure_item

    if created:
        ensure_item(instance)
    else:
        InventoryItem.objects.filter(product=instance, variant__isnull=True).exclude(sku=instance.sku).update(sku=instance.sku)
