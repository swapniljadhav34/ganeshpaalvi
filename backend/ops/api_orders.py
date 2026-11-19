"""
Order book API.

Staff (session + CSRF, permission-checked):     /api/staff/orders…
Customers (public, rate-limited, no login):      /api/orders/track…   (number + phone, or the secret link)
"""

import re
from datetime import date
from decimal import Decimal
from typing import Literal

from django.conf import settings
from django.db.models import Count, Max, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from ninja import Query, Router, Schema
from ninja.errors import HttpError
from pydantic import Field

from api.ratelimit import rate_limit
from catalog.models import Product
from leads.models import LeadInquiry
from storefront.models import BrandSettings

from .api import page_of, person, staff_router
from .inventory import StockError
from .models import Order
from .orders import create_order, public_status, recalc, set_status
from .permissions import needs
from .roles import has_perm

orders_public_router = Router(tags=["orders"])
S = Order.Status


def order_payload(o, detail=False):
    out = {
        "id": o.pk, "number": o.number, "created_at": o.created_at, "status": o.status, "status_label": o.get_status_display(),
        "source": o.source, "source_label": o.get_source_display(), "channel": o.channel,
        "customer_name": o.customer_name, "phone": o.phone, "business_name": o.business_name, "city": o.city,
        "total": o.total, "payment_status": o.payment_status, "payment_label": o.get_payment_status_display(),
        "items": getattr(o, "n_items", None), "created_by": person(o.created_by), "assigned_to": person(o.assigned_to),
    }
    if detail:
        out.update({
            "email": o.email, "gstin": o.gstin, "address": o.address, "state": o.state, "pincode": o.pincode,
            "subtotal": o.subtotal, "discount": o.discount, "shipping": o.shipping, "payment_mode": o.payment_mode,
            "courier": o.courier, "tracking_number": o.tracking_number, "expected_delivery": o.expected_delivery,
            "customer_note": o.customer_note, "internal_notes": o.internal_notes, "stock_state": o.stock_state,
            "stock_label": o.get_stock_state_display(), "lead_id": o.lead_id,
            "tracking_url": f"{settings.SITE_URL}/track/{o.tracking_token}",
            "lines": [{"id": ln.pk, "product_id": ln.product_id, "title": ln.title, "sku": ln.sku, "quantity": ln.quantity,
                       "unit_price": ln.unit_price, "line_total": ln.line_total} for ln in o.lines.all()],
            "events": [{"status": e.status, "label": S(e.status).label, "note": e.note, "at": e.at, "by": person(e.by)}
                       for e in o.events.select_related("by")],
            "next": [s.value for s in allowed_next(o)],
        })
    return out


def allowed_next(o):
    if o.status in (S.DELIVERED, S.CANCELLED):
        return []
    after = Order.FLOW[Order.FLOW.index(S(o.status)) + 1:]
    return [*after, S.CANCELLED]


def orders_qs():
    return Order.objects.select_related("created_by", "assigned_to").annotate(n_items=Sum("lines__quantity"))


class OrderQuery(Schema):
    status: str | None = Field(None, max_length=12)
    source: str | None = Field(None, max_length=10)
    q: str | None = Field(None, max_length=80)
    mine: bool = False
    page: int = Field(1, ge=1, le=5000)


@staff_router.get("/orders")
@needs("orders.view")
def orders_list(request, f: Query[OrderQuery]):
    qs = orders_qs()
    if f.status:
        qs = qs.filter(status=f.status)
    if f.source:
        qs = qs.filter(source=f.source)
    if f.mine:
        qs = qs.filter(Q(created_by=request.auth) | Q(assigned_to=request.auth))
    if f.q:
        digits = re.sub(r"\D", "", f.q)
        cond = Q(number__icontains=f.q) | Q(customer_name__icontains=f.q) | Q(business_name__icontains=f.q) | Q(city__icontains=f.q)
        if len(digits) >= 4:
            cond |= Q(phone__contains=digits[-10:])
        qs = qs.filter(cond)
    rows, has_next = page_of(qs, f.page)
    return {"orders": [order_payload(o) for o in rows], "has_next": has_next, "page": f.page,
            "counts": dict(Order.objects.values_list("status").annotate(n=Count("id"))),
            "statuses": [{"key": s.value, "label": s.label} for s in S],
            "sources": [{"key": s.value, "label": s.label} for s in Order.Source],
            "can_create": has_perm(request.auth, "orders.create"), "can_update": has_perm(request.auth, "orders.update")}


@staff_router.get("/orders/customers")
@needs("orders.view")
def orders_customers(request, q: str = ""):
    """Customer order book: one row per customer (phone), newest first."""
    qs = Order.objects.all()
    if q:
        digits = re.sub(r"\D", "", q)
        cond = Q(customer_name__icontains=q) | Q(business_name__icontains=q)
        if len(digits) >= 4:
            cond |= Q(phone__contains=digits[-10:])
        qs = qs.filter(cond)
    rows = (qs.values("phone").annotate(orders=Count("id"), spent=Sum("total", filter=~Q(status=S.CANCELLED)),
                                        last=Max("created_at"),
                                        open=Count("id", filter=~Q(status__in=[S.DELIVERED, S.CANCELLED])))
            .order_by("-last")[:200])
    names = {}
    for phone, name, biz, city in Order.objects.filter(phone__in=[r["phone"] for r in rows]).order_by("created_at") \
            .values_list("phone", "customer_name", "business_name", "city"):
        names[phone] = (name, biz, city)
    return {"customers": [{**r, "name": names.get(r["phone"], ("", "", ""))[0], "business_name": names.get(r["phone"], ("", "", ""))[1],
                           "city": names.get(r["phone"], ("", "", ""))[2]} for r in rows]}


@staff_router.get("/orders/pick/products")
@needs("orders.create")
def orders_pick_products(request, q: str = ""):
    qs = Product.objects.filter(Q(title__icontains=q) | Q(sku__icontains=q)).order_by("title")[:15]
    out = []
    for p in qs.prefetch_related("inventory_items"):
        item = next((i for i in p.inventory_items.all() if i.variant_id is None), None)
        out.append({"id": p.pk, "title": p.title, "sku": p.sku, "retail_price": p.retail_price,
                    "wholesale_price": p.wholesale_price, "available": item.available if item else None})
    return {"products": out}


@staff_router.get("/orders/{order_id}")
@needs("orders.view")
def orders_detail(request, order_id: int):
    return order_payload(get_object_or_404(orders_qs(), pk=order_id), detail=True)


class LineIn(Schema):
    product_id: int | None = None
    title: str = Field("", max_length=220)
    quantity: int = Field(..., ge=1, le=1_000_000)
    unit_price: Decimal = Field(..., ge=0, le=10_000_000, decimal_places=2)


class OrderIn(Schema):
    source: Literal[tuple(s.value for s in Order.Source)] = "PHONE"  # type: ignore[valid-type]
    channel: Literal["RETAIL", "WHOLESALE"] = "RETAIL"
    status: Literal["PENDING", "CONFIRMED", "PACKED", "IN_TRANSIT", "DELIVERED"] = "PENDING"
    customer_name: str = Field(..., min_length=1, max_length=120)
    phone: str = Field(..., min_length=6, max_length=20)
    email: str = Field("", max_length=254)
    business_name: str = Field("", max_length=140)
    gstin: str = Field("", max_length=15)
    address: str = Field("", max_length=1000)
    city: str = Field("", max_length=80)
    state: str = Field("", max_length=60)
    pincode: str = Field("", max_length=10)
    discount: Decimal = Field(Decimal("0"), ge=0, le=10_000_000)
    shipping: Decimal = Field(Decimal("0"), ge=0, le=10_000_000)
    payment_status: Literal["UNPAID", "PARTIAL", "PAID", "COD"] = "UNPAID"
    payment_mode: str = Field("", max_length=40)
    customer_note: str = Field("", max_length=500)
    internal_notes: str = Field("", max_length=4000)
    lead_id: int | None = None
    lines: list[LineIn] = Field(..., min_length=1, max_length=200)


def _norm_phone(p):
    digits = re.sub(r"[^\d+]", "", p)
    if len(re.sub(r"\D", "", digits)) < 6:
        raise HttpError(400, "Enter a valid phone number.")
    return digits


@staff_router.post("/orders")
@needs("orders.create")
def orders_create(request, payload: OrderIn):
    data = payload.dict(exclude={"lines", "lead_id"})
    data["phone"] = _norm_phone(data["phone"])
    if data["status"] != "PENDING" and not has_perm(request.auth, "orders.update"):
        raise HttpError(403, "You can log orders as Pending only.")
    if payload.lead_id:
        data["lead"] = LeadInquiry.objects.filter(pk=payload.lead_id).first()
    products = {p.pk: p for p in Product.objects.filter(pk__in=[ln.product_id for ln in payload.lines if ln.product_id])}
    lines = []
    for ln in payload.lines:
        p = products.get(ln.product_id) if ln.product_id else None
        if ln.product_id and p is None:
            raise HttpError(400, "One of the products no longer exists.")
        if p is None and not ln.title.strip():
            raise HttpError(400, "Give each custom line a name.")
        lines.append({"product": p, "title": ln.title.strip() or None, "quantity": ln.quantity, "unit_price": ln.unit_price})
    try:
        order = create_order(data, lines, request.auth)
    except StockError as e:
        raise HttpError(400, str(e)) from e
    return order_payload(get_object_or_404(orders_qs(), pk=order.pk), detail=True)


class OrderEditIn(Schema):
    customer_name: str | None = Field(None, min_length=1, max_length=120)
    phone: str | None = Field(None, min_length=6, max_length=20)
    email: str | None = Field(None, max_length=254)
    business_name: str | None = Field(None, max_length=140)
    gstin: str | None = Field(None, max_length=15)
    address: str | None = Field(None, max_length=1000)
    city: str | None = Field(None, max_length=80)
    state: str | None = Field(None, max_length=60)
    pincode: str | None = Field(None, max_length=10)
    discount: Decimal | None = Field(None, ge=0, le=10_000_000)
    shipping: Decimal | None = Field(None, ge=0, le=10_000_000)
    payment_status: Literal["UNPAID", "PARTIAL", "PAID", "COD"] | None = None
    payment_mode: str | None = Field(None, max_length=40)
    customer_note: str | None = Field(None, max_length=500)
    internal_notes: str | None = Field(None, max_length=4000)
    courier: str | None = Field(None, max_length=80)
    tracking_number: str | None = Field(None, max_length=80)
    expected_delivery: date | None = None


@staff_router.patch("/orders/{order_id}")
@needs("orders.update")
def orders_edit(request, order_id: int, payload: OrderEditIn):
    o = get_object_or_404(Order, pk=order_id)
    data = payload.dict(exclude_unset=True)
    if "phone" in data:
        data["phone"] = _norm_phone(data["phone"])
    for k, v in data.items():
        setattr(o, k, v)
    if {"discount", "shipping"} & set(data):
        recalc(o)
    o.save()
    return order_payload(get_object_or_404(orders_qs(), pk=o.pk), detail=True)


class StatusIn(Schema):
    status: Literal[tuple(s.value for s in S)]  # type: ignore[valid-type]
    note: str = Field("", max_length=300)
    courier: str | None = Field(None, max_length=80)
    tracking_number: str | None = Field(None, max_length=80)
    expected_delivery: date | None = None


@staff_router.post("/orders/{order_id}/status")
@needs("orders.update")
def orders_status(request, order_id: int, payload: StatusIn):
    get_object_or_404(Order, pk=order_id)
    try:
        set_status(order_id, payload.status, request.auth, note=payload.note, courier=payload.courier,
                   tracking_number=payload.tracking_number, expected_delivery=payload.expected_delivery)
    except StockError as e:
        raise HttpError(400, str(e)) from e
    return order_payload(get_object_or_404(orders_qs(), pk=order_id), detail=True)


@staff_router.delete("/orders/{order_id}")
@needs("orders.update")
def orders_delete(request, order_id: int):
    """Only a Pending order (no stock touched yet) may be deleted — e.g. logged by mistake. Others are cancelled."""
    o = get_object_or_404(Order, pk=order_id)
    if o.status != S.PENDING or o.stock_state != Order.StockState.NONE:
        raise HttpError(400, "Only pending orders can be deleted. Cancel this order instead, so stock stays correct.")
    o.delete()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Receipts (print-ready HTML: A4 or 80 mm thermal; "Save as PDF" from the print dialog)
# ---------------------------------------------------------------------------
def receipt_response(order, size="a4", public=False):
    brand = BrandSettings.load()
    html = render_to_string("ops/receipt.html", {
        "o": order, "lines": list(order.lines.all()), "brand": brand, "size": "thermal" if size == "thermal" else "a4",
        "public": public, "site_url": settings.SITE_URL,
    })
    resp = HttpResponse(html, content_type="text/html; charset=utf-8")
    resp["X-Robots-Tag"] = "noindex, nofollow"
    resp["Cache-Control"] = "no-store"
    return resp


@staff_router.get("/orders/{order_id}/receipt")
@needs("orders.view")
def orders_receipt(request, order_id: int, size: Literal["a4", "thermal"] = "a4"):
    return receipt_response(get_object_or_404(Order, pk=order_id), size)


# ---------------------------------------------------------------------------
# Customer tracking (public)
# ---------------------------------------------------------------------------
def _same_phone(a, b):
    da, db = re.sub(r"\D", "", a or ""), re.sub(r"\D", "", b or "")
    return len(da) >= 6 and len(db) >= 6 and da[-10:] == db[-10:]


class TrackQuery(Schema):
    number: str = Field(..., min_length=4, max_length=24)
    phone: str = Field(..., min_length=6, max_length=20)


@orders_public_router.get("/track")
@rate_limit("order_track", lambda: settings.RATE_LIMIT_TRACK_ORDER_PER_MIN)
def track_lookup(request, f: Query[TrackQuery]):
    o = Order.objects.filter(number__iexact=f.number.strip()).first()
    if not o or not _same_phone(o.phone, f.phone):  # same message either way: no order-number probing
        raise HttpError(404, "We couldn't find an order with that number and phone. Check both and try again.")
    return {**public_status(o), "token": o.tracking_token}


@orders_public_router.get("/track/{token}")
@rate_limit("order_track", lambda: settings.RATE_LIMIT_TRACK_ORDER_PER_MIN)
def track_token(request, token: str):
    o = Order.objects.filter(tracking_token=token[:24]).first()
    if not o:
        raise HttpError(404, "This tracking link isn't valid.")
    return {**public_status(o), "token": o.tracking_token}


@orders_public_router.get("/track/{token}/receipt")
@rate_limit("order_track", lambda: settings.RATE_LIMIT_TRACK_ORDER_PER_MIN)
def track_receipt(request, token: str, size: Literal["a4", "thermal"] = "a4"):
    o = Order.objects.filter(tracking_token=token[:24]).first()
    if not o:
        raise HttpError(404, "This link isn't valid.")
    return receipt_response(o, size, public=True)
