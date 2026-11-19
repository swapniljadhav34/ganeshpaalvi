"""
Order book: online and offline orders (phone, field, walk-in, WhatsApp) with a live status.

Status flow:   PENDING → CONFIRMED → PACKED → IN_TRANSIT → DELIVERED     (+ CANCELLED)
Orders only move forward (a walk-in sale may jump straight to DELIVERED). Stock follows the status,
always through ops.inventory.adjust_stock, so every piece is locked, logged and re-checked for alerts:

  CONFIRMED / PACKED        → pieces are RESERVED (they stay on the shelf but can't be promised twice)
  IN_TRANSIT / DELIVERED    → pieces leave stock (OUT, or WHOLESALE_DISPATCH for wholesale orders)
  CANCELLED before dispatch → the reservation is released
  CANCELLED while in transit→ the pieces come back into stock (IN, "returned")
"""

import secrets
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from .inventory import StockError, adjust_stock, ensure_item
from .models import InventoryItem, Order, OrderEvent, OrderLine

S = Order.Status
STOCK = Order.StockState
FLOW = Order.FLOW
CANCELLABLE = {S.PENDING, S.CONFIRMED, S.PACKED, S.IN_TRANSIT}


def _next_number():
    today = timezone.localdate()
    prefix = f"ORD-{today:%y%m%d}-"
    last = Order.objects.filter(number__startswith=prefix).order_by("-number").values_list("number", flat=True).first()
    n = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{n:04d}"


def _money(v):
    return Decimal(str(v or 0)).quantize(Decimal("0.01"))


def recalc(order):
    order.subtotal = sum((line.line_total for line in order.lines.all()), Decimal("0.00"))
    order.total = max(Decimal("0.00"), order.subtotal - _money(order.discount) + _money(order.shipping))


def create_order(data, lines, user=None):
    """data: customer & order fields. lines: [{product, quantity, unit_price, title?}] (product may be None)."""
    if not lines:
        raise StockError("Add at least one product.")
    data = dict(data)
    target = S(data.pop("status", S.PENDING))
    for attempt in range(5):
        try:
            with transaction.atomic():
                order = Order.objects.create(number=_next_number(), tracking_token=secrets.token_urlsafe(12)[:16],
                                             created_by=user, **data)
                for ln in lines:
                    p = ln.get("product")
                    item = ensure_item(p) if p is not None else None
                    OrderLine.objects.create(
                        order=order, product=p, item=item, quantity=int(ln["quantity"]),
                        title=(ln.get("title") or (p.title if p else "Item"))[:220], sku=(p.sku if p else ln.get("sku", ""))[:60],
                        unit_price=_money(ln["unit_price"]),
                    )
                recalc(order)
                order.save(update_fields=["subtotal", "total"])
                OrderEvent.objects.create(order=order, status=order.status, by=user,
                                          note=f"Order logged ({order.get_source_display()})")
                if target != S.PENDING:  # e.g. a walk-in sale logged as already delivered
                    set_status(order.pk, target, user)
            return Order.objects.get(pk=order.pk)
        except IntegrityError:
            if attempt == 4:
                raise
    raise RuntimeError("unreachable")


def _stock_lines(order):
    return [ln for ln in order.lines.select_related("item") if ln.item_id]


def _reserve(order, user):
    for ln in _stock_lines(order):
        item = InventoryItem.objects.select_for_update().get(pk=ln.item_id)
        if item.available < ln.quantity:
            raise StockError(f"Only {max(item.available, 0)} of {ln.title} available — can't reserve {ln.quantity}.")
        adjust_stock(item, "RESERVE", ln.quantity, f"Order {order.number} confirmed", user)


def _dispatch(order, user, reserved):
    kind = "WHOLESALE_DISPATCH" if order.channel == Order.Channel.WHOLESALE else "OUT"
    for ln in _stock_lines(order):
        adjust_stock(ln.item, kind, ln.quantity, f"Order {order.number} dispatched", user,
                     release_reserved=ln.quantity if reserved else 0)


def _release(order, user):
    for ln in _stock_lines(order):
        adjust_stock(ln.item, "RELEASE", ln.quantity, f"Order {order.number} cancelled", user)


def _return(order, user):
    for ln in _stock_lines(order):
        adjust_stock(ln.item, "IN", ln.quantity, f"Order {order.number} cancelled in transit — returned", user)


def set_status(order_id, new_status, user=None, *, note="", courier=None, tracking_number=None, expected_delivery=None):
    """Move an order to a new status and keep stock in step. Atomic: either everything happens or nothing."""
    new_status = S(new_status)
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        old = S(order.status)
        if old == new_status:
            raise StockError("The order is already at this status.")
        if old in (S.DELIVERED, S.CANCELLED):
            raise StockError(f"This order is {old.label.lower()} and can't change any more.")
        if new_status == S.CANCELLED:
            if old not in CANCELLABLE:
                raise StockError("This order can't be cancelled.")
            if order.stock_state == STOCK.RESERVED:
                _release(order, user)
                order.stock_state = STOCK.NONE
            elif order.stock_state == STOCK.DISPATCHED:
                _return(order, user)
                order.stock_state = STOCK.RETURNED
        else:
            if FLOW.index(new_status) < FLOW.index(old):
                raise StockError(f"Orders only move forward (it is already {old.label.lower()}).")
            if new_status in (S.CONFIRMED, S.PACKED) and order.stock_state == STOCK.NONE:
                _reserve(order, user)
                order.stock_state = STOCK.RESERVED
            if new_status in (S.IN_TRANSIT, S.DELIVERED) and order.stock_state in (STOCK.NONE, STOCK.RESERVED):
                _dispatch(order, user, reserved=order.stock_state == STOCK.RESERVED)
                order.stock_state = STOCK.DISPATCHED
        if courier is not None:
            order.courier = courier
        if tracking_number is not None:
            order.tracking_number = tracking_number
        if expected_delivery is not None:
            order.expected_delivery = expected_delivery
        order.status = new_status
        order.save()
        OrderEvent.objects.create(order=order, status=new_status, by=user, note=(note or "").strip()[:300])
    return order


def public_status(order):
    """What the customer may see: no internal notes, no staff names."""
    events = [{"status": e.status, "label": S(e.status).label, "at": e.at, "note": e.note if e.status != S.PENDING else ""}
              for e in order.events.all()]
    return {
        "number": order.number, "status": order.status, "status_label": order.get_status_display(),
        "steps": [{"key": s.value, "label": s.label} for s in FLOW], "events": events,
        "placed_at": order.created_at, "customer": order.customer_name.split(" ")[0],
        "courier": order.courier, "tracking_number": order.tracking_number, "expected_delivery": order.expected_delivery,
        "lines": [{"title": ln.title, "quantity": ln.quantity} for ln in order.lines.all()],
        "total": order.total, "customer_note": order.customer_note,
    }
