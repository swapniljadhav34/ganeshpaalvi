"""
The only place stock changes. Every change:
  1. runs inside a database transaction,
  2. locks the stock row (SELECT … FOR UPDATE) so two staff can't race each other,
  3. updates the numbers with F() expressions (no read-modify-write),
  4. writes a permanent StockMovement,
  5. re-checks the automatic alerts and the website's stock label.
"""

import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from catalog.models import Product
from storefront.utils import bump_catalog_version

from .models import InventoryAlert, InventoryItem, InventorySettings, ProductionBatch, StockMovement

log = logging.getLogger("paalvi")
K = StockMovement.Kind

# How each kind of movement changes (stock, reserved). ADJUSTMENT takes the sign you give it.
_EFFECT = {
    K.IN: (1, 0), K.PRODUCTION_IN: (1, 0), K.OUT: (-1, 0), K.DAMAGED: (-1, 0), K.WHOLESALE_DISPATCH: (-1, 0),
    K.ADJUSTMENT: (1, 0), K.RESERVE: (0, 1), K.RELEASE: (0, -1),
}
STAFF_KINDS = [k for k in K if k != K.PRODUCTION_IN]  # production stock only arrives via completed batches


class StockError(ValueError):
    """A stock change that would make no sense (e.g. selling more than you have)."""


def adjust_stock(item, kind, quantity, reason, user=None, *, batch_number="", production_batch=None, release_reserved=0):
    """Apply one stock change atomically and log it. Returns the StockMovement.

    quantity: pieces. For ADJUSTMENT it may be negative; for every other kind give a positive number.
    release_reserved: for OUT / WHOLESALE_DISPATCH, also release this many reserved pieces (order fulfilled).
    """
    kind = K(kind)
    quantity = int(quantity)
    reason = (reason or "").strip()
    if not reason:
        raise StockError("Please give a reason for this stock change.")
    if quantity == 0 or (kind != K.ADJUSTMENT and quantity < 0):
        raise StockError("Enter a quantity greater than zero.")
    s_sign, r_sign = _EFFECT[kind]
    d_stock, d_reserved = s_sign * quantity, r_sign * quantity
    if release_reserved and kind in (K.OUT, K.WHOLESALE_DISPATCH):
        d_reserved -= int(release_reserved)
    item_id = item.pk if isinstance(item, InventoryItem) else int(item)

    with transaction.atomic():
        locked = InventoryItem.objects.select_for_update().get(pk=item_id)
        if locked.stock_quantity + d_stock < 0:
            raise StockError(f"Only {locked.stock_quantity} in stock — you can't remove {abs(d_stock)}.")
        if locked.reserved_quantity + d_reserved < 0:
            raise StockError(f"Only {locked.reserved_quantity} reserved — you can't release {abs(d_reserved)}.")
        InventoryItem.objects.filter(pk=item_id).update(
            stock_quantity=F("stock_quantity") + d_stock,
            reserved_quantity=F("reserved_quantity") + d_reserved,
            updated_at=timezone.now(),
        )
        locked.refresh_from_db()
        movement = StockMovement.objects.create(
            item=locked, kind=kind, quantity=d_stock if d_stock else d_reserved,
            stock_after=locked.stock_quantity, reserved_after=locked.reserved_quantity, reason=reason[:300],
            batch_number=batch_number or locked.batch_number, production_batch=production_batch, performed_by=user,
        )
        evaluate_alerts(locked)
        sync_storefront(locked)
    return movement


# ---------------------------------------------------------------------------
# Automatic alerts
# ---------------------------------------------------------------------------
def wanted_alerts(item, *, today=None, cfg=None):
    """Which alerts SHOULD be active for this item right now → {kind: message}."""
    cfg = cfg or InventorySettings.load()
    today = today or timezone.localdate()
    avail = item.available
    wanted = {}
    A = InventoryAlert.Kind
    if avail <= 0:
        wanted[A.OUT_OF_STOCK] = "Out of stock" + (f" ({item.reserved_quantity} reserved for orders)" if item.reserved_quantity else "")
    elif avail <= item.low_stock_threshold:
        wanted[A.LOW_STOCK] = f"Only {avail} available (alert at {item.low_stock_threshold})"
    if item.expiry_date and item.stock_quantity > 0 and item.expiry_date <= today + timedelta(days=cfg.expiry_warning_days):
        days = (item.expiry_date - today).days
        wanted[A.EXPIRING_SOON] = (f"Batch {item.batch_number or '—'} expired {-days} day(s) ago" if days < 0
                                   else f"Batch {item.batch_number or '—'} expires in {days} day(s) ({item.expiry_date:%d %b %Y})")
    if avail < item.reorder_point and not item.production_batches.filter(status__in=ProductionBatch.ACTIVE).exists():
        wanted[A.PRODUCTION_NEEDED] = f"{avail} available, below reorder point {item.reorder_point} — no batch planned"
    return wanted


def evaluate_alerts(item, *, today=None, cfg=None):
    """Raise new alerts, refresh messages, and resolve alerts that no longer apply."""
    wanted = wanted_alerts(item, today=today, cfg=cfg)
    active = {a.kind: a for a in item.alerts.filter(is_active=True)}
    now = timezone.now()
    for kind, message in wanted.items():
        current = active.get(kind)
        if current is None:
            try:
                with transaction.atomic():  # savepoint: a parallel request may have raised it already
                    InventoryAlert.objects.create(item=item, kind=kind, message=message[:200])
            except IntegrityError:
                pass
        elif current.message != message:
            InventoryAlert.objects.filter(pk=current.pk).update(message=message[:200])
    gone = [a.pk for kind, a in active.items() if kind not in wanted]
    if gone:
        InventoryAlert.objects.filter(pk__in=gone).update(is_active=False, resolved_at=now)


def storefront_label(item):
    avail = item.available
    if avail <= 0:
        return Product.StockStatus.OUT
    if avail <= item.low_stock_threshold:
        return Product.StockStatus.LOW
    return Product.StockStatus.IN_STOCK


def sync_storefront(item, cfg=None):
    """Keep the website's stock label in step with real stock (made-to-order items are left alone)."""
    cfg = cfg or InventorySettings.load()
    if not cfg.sync_storefront_status:
        return
    label = storefront_label(item)
    target = item.variant if item.variant_id else item.product
    if target.stock_status in (Product.StockStatus.MADE_TO_ORDER, label):
        return
    type(target).objects.filter(pk=target.pk).update(stock_status=label)
    transaction.on_commit(bump_catalog_version)


def ensure_item(product, variant=None):
    """The stock item for a product (or variant), created with the default thresholds if missing."""
    cfg = InventorySettings.load()
    lookup = {"product": product, "variant": variant}
    item = InventoryItem.objects.filter(**lookup).first()
    if item:
        return item
    sku = (variant.sku if variant and variant.sku else f"{product.sku}-{variant.pk}" if variant else product.sku)[:60]
    try:
        with transaction.atomic():
            item = InventoryItem.objects.create(
                sku=sku, low_stock_threshold=cfg.default_low_stock_threshold, reorder_point=cfg.default_reorder_point, **lookup)
    except IntegrityError:
        return InventoryItem.objects.get(**lookup)
    evaluate_alerts(item, cfg=cfg)
    return item


def check_all(today=None):
    """Nightly sweep: expiry dates move closer every day even when nobody touches stock."""
    cfg = InventorySettings.load()
    n = 0
    for item in InventoryItem.objects.select_related("product", "variant").iterator(chunk_size=500):
        evaluate_alerts(item, today=today, cfg=cfg)
        n += 1
    return n
