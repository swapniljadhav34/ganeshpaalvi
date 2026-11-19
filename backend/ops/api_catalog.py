"""
Product & category controls in Studio (quick actions next to the full editor in the Designer workspace):

  • delete a product permanently (its stock history and invoices stay, labelled with the old name)
  • reset stock to zero in one click (logged as a stock count correction, like every stock change)
  • add / rename / delete categories (moving or deleting their products)
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from ninja import Schema
from ninja.errors import HttpError
from pydantic import Field

from catalog.models import Category, Product
from storefront.utils import clear_site_cache

from .api import staff_router
from .inventory import StockError, adjust_stock
from .models import InventoryItem
from .permissions import needs


def delete_product(p):
    """Delete a product and its files. Stock movements, batches, orders and invoices keep their history."""
    files = [p.model_3d, p.model_poster, *[img.image for img in p.images.all()]]
    with transaction.atomic():
        p.delete()
    for f in files:  # after the commit: never delete files for a product that still exists
        if f:
            try:
                f.storage.delete(f.name)
            except Exception:  # a missing file must not break the delete
                pass
    clear_site_cache()


@staff_router.delete("/catalog/products/{product_id}")
@needs("catalog.delete")
def catalog_delete_product(request, product_id: int):
    p = get_object_or_404(Product, pk=product_id)
    title = p.title
    delete_product(p)
    return {"ok": True, "deleted": title}


def zero_item(item, user):
    """Stock → 0, logged. Reserved pieces stay reserved, so open orders show up as 'Out of stock'."""
    with transaction.atomic():
        locked = InventoryItem.objects.select_for_update().get(pk=item.pk)
        if locked.stock_quantity == 0:
            return None
        return adjust_stock(locked, "ADJUSTMENT", -locked.stock_quantity, "Stock reset to zero (quick action)", user)


@staff_router.post("/inventory/items/{item_id}/zero")
@needs("inventory.reset")
def inventory_zero(request, item_id: int):
    from .api import item_payload, items_qs

    item = get_object_or_404(InventoryItem, pk=item_id)
    try:
        zero_item(item, request.auth)
    except StockError as e:
        raise HttpError(400, str(e)) from e
    return item_payload(items_qs().get(pk=item_id), request)


@staff_router.post("/catalog/products/{product_id}/zero-stock")
@needs("inventory.reset")
def catalog_zero_stock(request, product_id: int):
    p = get_object_or_404(Product, pk=product_id)
    n = sum(1 for item in InventoryItem.objects.filter(product=p) if zero_item(item, request.auth))
    return {"ok": True, "items_reset": n}


# ---- Categories ----
def category_payload(c):
    return {"id": c.pk, "name": c.name, "slug": c.slug, "products": getattr(c, "n", None), "is_active": getattr(c, "is_active", True)}


@staff_router.get("/catalog/categories")
@needs("catalog.edit")
def categories(request):
    from django.db.models import Count

    return {"categories": [category_payload(c) for c in Category.objects.annotate(n=Count("products")).order_by("name")]}


class CategoryIn(Schema):
    name: str = Field(..., min_length=1, max_length=80)


@staff_router.post("/catalog/categories")
@needs("catalog.edit")
def category_create(request, payload: CategoryIn):
    c = Category.objects.create(name=payload.name.strip())
    clear_site_cache()
    return category_payload(c)


@staff_router.patch("/catalog/categories/{category_id}")
@needs("catalog.edit")
def category_rename(request, category_id: int, payload: CategoryIn):
    c = get_object_or_404(Category, pk=category_id)
    c.name = payload.name.strip()
    c.save()
    clear_site_cache()
    return category_payload(c)


@staff_router.delete("/catalog/categories/{category_id}")
@needs("catalog.delete")
def category_delete(request, category_id: int, move_to: int | None = None, delete_products: bool = False):
    c = get_object_or_404(Category, pk=category_id)
    products = list(Product.objects.filter(category=c))
    if products and move_to is None and not delete_products:
        raise HttpError(400, f"{len(products)} product(s) are in this category. Move them to another category or delete them too.")
    if move_to is not None:
        target = get_object_or_404(Category, pk=move_to)
        if target.pk == c.pk:
            raise HttpError(400, "Choose a different category.")
        Product.objects.filter(category=c).update(category=target)
    elif delete_products:
        for p in products:
            delete_product(p)
    Category.objects.filter(parent=c).update(parent=None)  # sub-categories move up a level instead of vanishing
    c.delete()
    clear_site_cache()
    return {"ok": True}
