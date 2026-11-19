"""
Paalvi Studio API (mounted at /api/staff/) and the public analytics beacon (/api/analytics/).

Security model
  • Session login (Django auth + django-axes lockout) — no tokens in the browser's storage.
  • Every endpoint below `staff_router` requires a logged-in session AND passes Django's CSRF check
    (Ninja's django_auth), then `@needs(...)` checks the role's permissions on the server.
  • Accounting endpoints are reachable only with accounting.* permissions (super admin, accountant).
"""

import secrets
from datetime import date, timedelta
from typing import Literal

from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.http import FileResponse, Http404
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import File, Form, Query, Router, Schema
from ninja.errors import HttpError
from ninja.files import UploadedFile
from ninja.security import django_auth
from ninja.utils import check_csrf
from pydantic import Field

from api.ratelimit import rate_limit
from api.serializers import media_url, spec_url
from catalog.models import Product, ProductImage
from leads.models import LeadInquiry
from storefront import validators as V

from . import accounting as acc
from . import analytics
from .inventory import STAFF_KINDS, StockError, adjust_stock, ensure_item, evaluate_alerts, sync_storefront
from .models import (
    Expense,
    InventoryAlert,
    InventoryItem,
    InventorySettings,
    Invoice,
    ProductionBatch,
    StaffProfile,
    StockMovement,
)
from .permissions import needs
from .production import create_batch, move_batch
from .roles import ROLE_PERMISSIONS, Role, has_perm, user_permissions, user_role, user_tabs

User = get_user_model()
staff_router = Router(auth=django_auth, tags=["studio"])
analytics_router = Router(tags=["analytics"])
PAGE = 50


def page_of(qs, page, size=PAGE):
    start = (page - 1) * size
    rows = list(qs[start:start + size + 1])
    return rows[:size], len(rows) > size


def person(u):
    return {"id": u.pk, "name": u.get_full_name() or u.get_username()} if u else None


def bad(e):
    msg = "; ".join(e.messages) if isinstance(e, ValidationError) else str(e)
    raise HttpError(400, msg)


# ===========================================================================
# Auth
# ===========================================================================
class LoginIn(Schema):
    username: str = Field(..., min_length=1, max_length=150)
    password: str = Field(..., min_length=1, max_length=256)


def me_payload(user):
    role = user_role(user)
    return {
        "user": {"id": user.pk, "username": user.get_username(), "name": user.get_full_name() or user.get_username(), "email": user.email},
        "role": role.value, "role_label": role.label,
        "permissions": sorted(user_permissions(user)), "tabs": user_tabs(user),
        "admin_url": f"/{settings.ADMIN_URL}" if role == Role.SUPER_ADMIN else None,
    }


@staff_router.get("/auth/csrf", auth=None)
def csrf(request):
    """Sets the CSRF cookie the Studio sends back on every change."""
    return {"csrftoken": get_token(request)}


@staff_router.post("/auth/login", auth=None)
@rate_limit("login", lambda: settings.RATE_LIMIT_LOGIN_PER_MIN)
def staff_login(request, payload: LoginIn):
    if check_csrf(request):
        raise HttpError(403, "Your session expired. Refresh the page and try again.")
    user = authenticate(request, username=payload.username.strip(), password=payload.password)
    if user is None:
        if getattr(request, "axes_locked_out", False):
            raise HttpError(429, "Too many wrong attempts. This login is locked for one hour.")
        raise HttpError(401, "Wrong username or password.")
    if user_role(user) is None:
        raise HttpError(403, "This account doesn't have Studio access. Ask the owner to give you a role.")
    login(request, user)
    return me_payload(user)


@staff_router.post("/auth/logout")
def staff_logout(request):
    logout(request)
    return {"ok": True}


@staff_router.get("/auth/me")
def me(request):
    if user_role(request.auth) is None:
        raise HttpError(403, "This account doesn't have Studio access.")
    return me_payload(request.auth)


# ===========================================================================
# Inventory
# ===========================================================================
ALERT_ORDER = ["OUT_OF_STOCK", "PRODUCTION_NEEDED", "EXPIRING_SOON", "LOW_STOCK"]


def item_payload(i, request=None):
    alerts = getattr(i, "active_alerts", None)
    if alerts is None:
        alerts = list(i.alerts.filter(is_active=True))
    imgs = getattr(i.product, "first_images", None)
    thumb = spec_url(request, imgs[0].thumb) if imgs else None
    return {
        "id": i.pk, "sku": i.sku, "title": i.product.title, "variant": i.variant.value if i.variant_id else None,
        "product_id": i.product_id, "product_slug": i.product.slug, "thumb": thumb,
        "category": i.product.category.name if i.product.category_id else "",
        "stock": i.stock_quantity, "reserved": i.reserved_quantity, "available": i.available,
        "low_stock_threshold": i.low_stock_threshold, "reorder_point": i.reorder_point,
        "batch_number": i.batch_number, "expiry_date": i.expiry_date,
        "alerts": sorted([{"kind": a.kind, "label": a.get_kind_display(), "message": a.message} for a in alerts],
                         key=lambda a: ALERT_ORDER.index(a["kind"])),
        "active_batches": getattr(i, "n_batches", None),
        "updated_at": i.updated_at,
    }


def items_qs():
    active = InventoryAlert.objects.filter(is_active=True)
    return (InventoryItem.objects.select_related("product__category", "variant")
            .prefetch_related(Prefetch("alerts", queryset=active, to_attr="active_alerts"),
                              Prefetch("product__images", queryset=ProductImage.objects.order_by("order"), to_attr="first_images"))
            .annotate(n_batches=Count("production_batches", filter=Q(production_batches__status__in=ProductionBatch.ACTIVE), distinct=True)))


class ItemsQuery(Schema):
    q: str | None = Field(None, max_length=80)
    flag: Literal["OUT_OF_STOCK", "LOW_STOCK", "EXPIRING_SOON", "PRODUCTION_NEEDED", "ANY", "OK"] | None = None
    page: int = Field(1, ge=1, le=5000)


@staff_router.get("/inventory/items")
@needs("inventory.view")
def inventory_items(request, f: Query[ItemsQuery]):
    qs = items_qs()
    if f.q:
        qs = qs.filter(Q(sku__icontains=f.q) | Q(product__title__icontains=f.q) | Q(batch_number__icontains=f.q))
    has_alert = InventoryAlert.objects.filter(item=OuterRef("pk"), is_active=True)
    if f.flag == "ANY":
        qs = qs.filter(Exists(has_alert))
    elif f.flag == "OK":
        qs = qs.exclude(Exists(has_alert))
    elif f.flag:
        qs = qs.filter(Exists(has_alert.filter(kind=f.flag)))
    qs = qs.annotate(flagged=Exists(has_alert)).order_by("-flagged", "product__title", "sku")
    rows, has_next = page_of(qs, f.page)
    counts = dict(InventoryAlert.objects.filter(is_active=True).values_list("kind").annotate(n=Count("id")))
    return {"items": [item_payload(i, request) for i in rows], "has_next": has_next, "page": f.page,
            "alert_counts": counts, "total_items": InventoryItem.objects.count()}


@staff_router.get("/inventory/alerts")
@needs("inventory.view")
def inventory_alerts(request):
    rows = InventoryAlert.objects.filter(is_active=True).select_related("item__product", "item__variant")[:300]
    out = [{"id": a.pk, "kind": a.kind, "label": a.get_kind_display(), "message": a.message, "raised_at": a.raised_at,
            "item": {"id": a.item_id, "sku": a.item.sku, "title": a.item.label}} for a in rows]
    out.sort(key=lambda a: ALERT_ORDER.index(a["kind"]))
    return {"alerts": out}


class AdjustIn(Schema):
    kind: Literal[tuple(k.value for k in STAFF_KINDS)]  # type: ignore[valid-type]
    quantity: int = Field(..., ge=-1_000_000, le=1_000_000)
    reason: str = Field(..., min_length=3, max_length=300)
    release_reserved: int = Field(0, ge=0, le=1_000_000)


@staff_router.post("/inventory/items/{item_id}/adjust")
@needs("inventory.adjust")
def inventory_adjust(request, item_id: int, payload: AdjustIn):
    item = get_object_or_404(InventoryItem, pk=item_id)
    try:
        adjust_stock(item, payload.kind, payload.quantity, payload.reason, request.auth, release_reserved=payload.release_reserved)
    except StockError as e:
        bad(e)
    return item_payload(items_qs().get(pk=item_id), request)


class BatchInfoIn(Schema):
    batch_number: str = Field("", max_length=40)
    expiry_date: date | None = None


@staff_router.patch("/inventory/items/{item_id}/batch")
@needs("inventory.batches")
def inventory_batch(request, item_id: int, payload: BatchInfoIn):
    item = get_object_or_404(InventoryItem, pk=item_id)
    item.batch_number, item.expiry_date = payload.batch_number.strip(), payload.expiry_date
    item.save(update_fields=["batch_number", "expiry_date", "updated_at"])
    evaluate_alerts(item)
    return item_payload(items_qs().get(pk=item_id), request)


class ThresholdIn(Schema):
    low_stock_threshold: int = Field(..., ge=0, le=1_000_000)
    reorder_point: int = Field(..., ge=0, le=1_000_000)


@staff_router.patch("/inventory/items/{item_id}/thresholds")
@needs("inventory.configure")
def inventory_thresholds(request, item_id: int, payload: ThresholdIn):
    item = get_object_or_404(InventoryItem, pk=item_id)
    item.low_stock_threshold, item.reorder_point = payload.low_stock_threshold, payload.reorder_point
    item.save(update_fields=["low_stock_threshold", "reorder_point", "updated_at"])
    evaluate_alerts(item)
    sync_storefront(item)
    return item_payload(items_qs().get(pk=item_id), request)


class InvSettingsIn(Schema):
    expiry_warning_days: int = Field(..., ge=1, le=365)
    default_low_stock_threshold: int = Field(..., ge=0, le=1_000_000)
    default_reorder_point: int = Field(..., ge=0, le=1_000_000)
    sync_storefront_status: bool


@staff_router.get("/inventory/settings")
@needs("inventory.configure")
def inventory_settings(request):
    s = InventorySettings.load()
    return {k: getattr(s, k) for k in InvSettingsIn.model_fields}


@staff_router.put("/inventory/settings")
@needs("inventory.configure")
def inventory_settings_save(request, payload: InvSettingsIn):
    s = InventorySettings.load()
    for k, v in payload.dict().items():
        setattr(s, k, v)
    s.save()
    from .inventory import check_all

    check_all()  # a new expiry window changes which items are flagged
    return {k: getattr(s, k) for k in InvSettingsIn.model_fields}


class NewItemIn(Schema):
    product_id: int
    variant_id: int | None = None


@staff_router.post("/inventory/items")
@needs("inventory.configure")
def inventory_add_item(request, payload: NewItemIn):
    product = get_object_or_404(Product, pk=payload.product_id)
    variant = get_object_or_404(product.variants, pk=payload.variant_id) if payload.variant_id else None
    item = ensure_item(product, variant)
    return item_payload(items_qs().get(pk=item.pk), request)


class MovementsQuery(Schema):
    item: int | None = None
    kind: str | None = Field(None, max_length=20)
    q: str | None = Field(None, max_length=80)
    page: int = Field(1, ge=1, le=5000)


@staff_router.get("/inventory/movements")
@needs("inventory.audit")
def inventory_movements(request, f: Query[MovementsQuery]):
    qs = StockMovement.objects.select_related("item__product", "item__variant", "performed_by", "production_batch")
    if f.item:
        qs = qs.filter(item_id=f.item)
    if f.kind:
        qs = qs.filter(kind=f.kind)
    if f.q:
        qs = qs.filter(Q(item__sku__icontains=f.q) | Q(reason__icontains=f.q) | Q(item__product__title__icontains=f.q))
    rows, has_next = page_of(qs, f.page)
    return {"movements": [{
        "id": m.pk, "at": m.created_at, "kind": m.kind, "label": m.get_kind_display(), "quantity": m.quantity,
        "stock_after": m.stock_after, "reserved_after": m.reserved_after, "reason": m.reason, "batch_number": m.batch_number,
        "production_batch": m.production_batch.batch_code if m.production_batch_id else None,
        "item": {"id": m.item_id, "sku": m.item.sku, "title": m.item.label}, "by": person(m.performed_by),
    } for m in rows], "has_next": has_next, "page": f.page}


@staff_router.get("/inventory/export.csv")
@needs("inventory.export")
def inventory_export(request):
    rows = (InventoryItem.objects.select_related("product__category", "variant").prefetch_related(
        Prefetch("alerts", queryset=InventoryAlert.objects.filter(is_active=True), to_attr="active_alerts")).order_by("sku"))
    return acc.csv_response(
        f"paalvi-stock-{timezone.localdate()}.csv",
        ["SKU", "Product", "Variant", "Category", "In stock", "Reserved", "Available", "Low-stock alert at", "Reorder point",
         "Batch", "Expiry", "Alerts"],
        ([i.sku, i.product.title, i.variant.value if i.variant_id else "", i.product.category.name, i.stock_quantity,
          i.reserved_quantity, i.available, i.low_stock_threshold, i.reorder_point, i.batch_number, i.expiry_date or "",
          ", ".join(a.get_kind_display() for a in i.active_alerts)] for i in rows))


# ===========================================================================
# Production
# ===========================================================================
def batch_payload(b):
    today = timezone.localdate()
    active = b.status in ProductionBatch.ACTIVE
    return {
        "id": b.pk, "batch_code": b.batch_code, "status": b.status, "status_label": b.get_status_display(),
        "item": {"id": b.item_id, "sku": b.item.sku, "title": b.item.label, "available": b.item.available,
                 "alerts": [a.kind for a in getattr(b.item, "active_alerts", [])]},
        "planned_quantity": b.planned_quantity, "completed_quantity": b.completed_quantity, "wastage_quantity": b.wastage_quantity,
        "start_date": b.start_date, "expected_completion_date": b.expected_completion_date, "completed_at": b.completed_at,
        "expiry_date": b.expiry_date, "assigned_to": person(b.assigned_to), "notes": b.notes,
        "overdue": bool(active and b.expected_completion_date and b.expected_completion_date < today),
    }


def batches_qs():
    return ProductionBatch.objects.select_related("item__product", "item__variant", "assigned_to").prefetch_related(
        Prefetch("item__alerts", queryset=InventoryAlert.objects.filter(is_active=True), to_attr="active_alerts"))


class BatchQuery(Schema):
    mine: bool = False
    q: str | None = Field(None, max_length=80)


@staff_router.get("/production/batches")
@needs("production.view")
def production_batches(request, f: Query[BatchQuery]):
    recent = timezone.now() - timedelta(days=30)
    qs = batches_qs().filter(Q(status__in=ProductionBatch.ACTIVE) | Q(updated_at__gte=recent))
    if f.mine:
        qs = qs.filter(assigned_to=request.auth)
    if f.q:
        qs = qs.filter(Q(batch_code__icontains=f.q) | Q(item__sku__icontains=f.q) | Q(item__product__title__icontains=f.q))
    return {"batches": [batch_payload(b) for b in qs.order_by("expected_completion_date", "pk")[:500]],
            "statuses": [{"key": s.value, "label": s.label} for s in ProductionBatch.Status],
            "can_manage": has_perm(request.auth, "production.manage")}


def production_staff():
    allowed_roles = [r for r in Role if "production.update" in ROLE_PERMISSIONS[r]]
    return User.objects.filter(is_active=True).filter(
        Q(is_superuser=True) | Q(staff_profile__is_active=True, staff_profile__role__in=allowed_roles)).order_by("first_name", "username")


@staff_router.get("/production/assignees")
@needs("production.manage")
def production_assignees(request):
    return {"people": [person(u) for u in production_staff()]}


class BatchIn(Schema):
    item_id: int
    planned_quantity: int = Field(..., ge=1, le=10_000_000)
    assigned_to_id: int | None = None
    start_date: date | None = None
    expected_completion_date: date | None = None
    expiry_date: date | None = None
    notes: str = Field("", max_length=2000)


def _assignee(uid):
    if uid is None:
        return None
    user = production_staff().filter(pk=uid).first()
    if not user:
        raise HttpError(400, "That person can't be assigned production work.")
    return user


@staff_router.post("/production/batches")
@needs("production.manage")
def production_create(request, payload: BatchIn):
    item = get_object_or_404(InventoryItem, pk=payload.item_id)
    try:
        b = create_batch(item, payload.planned_quantity, request.auth, assigned_to=_assignee(payload.assigned_to_id),
                         start_date=payload.start_date, expected_completion_date=payload.expected_completion_date,
                         expiry_date=payload.expiry_date, notes=payload.notes)
    except StockError as e:
        bad(e)
    return batch_payload(batches_qs().get(pk=b.pk))


class MoveIn(Schema):
    status: Literal[tuple(s.value for s in ProductionBatch.Status)]  # type: ignore[valid-type]
    completed_quantity: int | None = Field(None, ge=0, le=10_000_000)
    wastage_quantity: int | None = Field(None, ge=0, le=10_000_000)
    notes: str | None = Field(None, max_length=1000)


@staff_router.post("/production/batches/{batch_id}/move")
@needs("production.update")
def production_move(request, batch_id: int, payload: MoveIn):
    b = get_object_or_404(ProductionBatch, pk=batch_id)
    manager = has_perm(request.auth, "production.manage")
    if not manager and b.assigned_to_id != request.auth.pk:
        raise HttpError(403, "Only the person assigned to this batch (or a production manager) can update it.")
    if payload.status == ProductionBatch.Status.CANCELLED and not manager:
        raise HttpError(403, "Only a production manager can cancel a batch.")
    try:
        move_batch(b.pk, payload.status, request.auth, completed_quantity=payload.completed_quantity,
                   wastage_quantity=payload.wastage_quantity, notes=payload.notes)
    except StockError as e:
        bad(e)
    return batch_payload(batches_qs().get(pk=b.pk))


class BatchEditIn(Schema):
    planned_quantity: int | None = Field(None, ge=1, le=10_000_000)
    assigned_to_id: int | None = None
    expected_completion_date: date | None = None
    expiry_date: date | None = None
    notes: str | None = Field(None, max_length=2000)


@staff_router.patch("/production/batches/{batch_id}")
@needs("production.manage")
def production_edit(request, batch_id: int, payload: BatchEditIn):
    with transaction.atomic():
        b = get_object_or_404(ProductionBatch.objects.select_for_update(), pk=batch_id)
        if b.status in (ProductionBatch.Status.COMPLETED, ProductionBatch.Status.CANCELLED):
            raise HttpError(400, "Finished batches can't be edited.")
        data = payload.dict(exclude_unset=True)
        if "assigned_to_id" in data:
            b.assigned_to = _assignee(data.pop("assigned_to_id"))
        for k, v in data.items():
            setattr(b, k, v)
        b.save()
    return batch_payload(batches_qs().get(pk=b.pk))


# ===========================================================================
# Accounting (super admin + accountant only)
# ===========================================================================
def _range(start, end):
    today = timezone.localdate()
    end = end or today
    start = start or end.replace(day=1)
    if start > end:
        raise HttpError(400, "The start date must be before the end date.")
    if (end - start).days > 3 * 366:
        raise HttpError(400, "Please choose a range of 3 years or less.")
    return start, end


class RangeQuery(Schema):
    start: date | None = None
    end: date | None = None


@staff_router.get("/accounting/summary")
@needs("accounting.view")
def accounting_summary(request, f: Query[RangeQuery]):
    return acc.summary(*_range(f.start, f.end))


def invoice_payload(i, detail=False):
    data = {
        "id": i.pk, "number": i.number, "channel": i.channel, "customer_name": i.customer_name, "customer_gstin": i.customer_gstin,
        "issue_date": i.issue_date, "due_date": i.due_date, "subtotal": i.subtotal, "cgst": i.cgst, "sgst": i.sgst, "igst": i.igst,
        "total": i.total, "amount_paid": i.amount_paid, "balance": i.balance, "payment_status": i.payment_status,
        "payment_status_label": i.get_payment_status_display(), "tax_mode": i.tax_mode,
    }
    if detail:
        data.update({
            "customer_phone": i.customer_phone, "customer_email": i.customer_email, "billing_address": i.billing_address,
            "place_of_supply": i.place_of_supply, "prices_include_tax": i.prices_include_tax, "notes": i.notes,
            "lead_id": i.lead_id,
            "lines": [{"description": ln.description, "hsn": ln.hsn, "quantity": ln.quantity, "unit_price": ln.unit_price,
                       "gst_rate": ln.gst_rate, "taxable_value": ln.taxable_value, "tax_amount": ln.tax_amount} for ln in i.lines.all()],
            "payments": [{"id": p.pk, "amount": p.amount, "mode": p.mode, "mode_label": p.get_mode_display(), "reference_id": p.reference_id,
                          "paid_on": p.paid_on, "notes": p.notes, "by": person(p.recorded_by)} for p in i.payments.select_related("recorded_by")],
        })
    return data


class InvoiceQuery(Schema):
    status: Literal["UNPAID", "PARTIAL", "PAID", "OVERDUE", "OPEN"] | None = None
    channel: Literal["retail", "wholesale"] | None = None
    q: str | None = Field(None, max_length=80)
    page: int = Field(1, ge=1, le=5000)


@staff_router.get("/accounting/invoices")
@needs("accounting.view")
def accounting_invoices(request, f: Query[InvoiceQuery]):
    acc.refresh_overdue()
    qs = Invoice.objects.all()
    if f.status == "OPEN":
        qs = qs.exclude(payment_status=Invoice.PaymentStatus.PAID)
    elif f.status:
        qs = qs.filter(payment_status=f.status)
    if f.channel:
        qs = qs.filter(channel=f.channel)
    if f.q:
        qs = qs.filter(Q(number__icontains=f.q) | Q(customer_name__icontains=f.q) | Q(customer_gstin__icontains=f.q))
    rows, has_next = page_of(qs, f.page)
    return {"invoices": [invoice_payload(i) for i in rows], "has_next": has_next, "page": f.page}


@staff_router.get("/accounting/invoices/{invoice_id}")
@needs("accounting.view")
def accounting_invoice(request, invoice_id: int):
    return invoice_payload(get_object_or_404(Invoice.objects.prefetch_related("lines"), pk=invoice_id), detail=True)


class LineIn(Schema):
    description: str = Field(..., min_length=1, max_length=200)
    hsn: str = Field("", max_length=10)
    quantity: float = Field(..., gt=0, le=10_000_000)
    unit_price: float = Field(..., ge=0, le=100_000_000)
    gst_rate: Literal[0, 5, 12, 18, 28] = 18
    product_id: int | None = None


class InvoiceIn(Schema):
    channel: Literal["retail", "wholesale"] = "wholesale"
    customer_name: str = Field(..., min_length=1, max_length=140)
    customer_phone: str = Field("", max_length=20)
    customer_email: str = Field("", max_length=254)
    customer_gstin: str = Field("", max_length=15, pattern=r"^$|^[0-9A-Z]{15}$")
    billing_address: str = Field("", max_length=1000)
    place_of_supply: str = Field("", max_length=60)
    tax_mode: Literal["intra", "inter"] = "intra"
    prices_include_tax: bool = False
    issue_date: date | None = None
    due_date: date | None = None
    notes: str = Field("", max_length=2000)
    lead_id: int | None = None
    lines: list[LineIn] = Field(..., min_length=1, max_length=100)


@staff_router.post("/accounting/invoices")
@needs("accounting.edit")
def accounting_invoice_create(request, payload: InvoiceIn):
    from decimal import Decimal

    data = payload.dict(exclude={"lines", "lead_id"})
    if payload.customer_email:
        try:
            forms.EmailField().clean(payload.customer_email)
        except ValidationError:
            raise HttpError(400, "Please enter a valid customer email (or leave it empty).")
    data["lead"] = LeadInquiry.objects.filter(pk=payload.lead_id).first() if payload.lead_id else None
    lines = []
    for ln in payload.lines:
        lines.append({"description": ln.description, "hsn": ln.hsn, "quantity": Decimal(str(ln.quantity)),
                      "unit_price": Decimal(str(ln.unit_price)), "gst_rate": Decimal(ln.gst_rate),
                      "product": Product.objects.filter(pk=ln.product_id).first() if ln.product_id else None})
    try:
        inv = acc.create_invoice(data, lines, request.auth)
    except acc.AccountingError as e:
        bad(e)
    return invoice_payload(inv, detail=True)


@staff_router.delete("/accounting/invoices/{invoice_id}")
@needs("accounting.edit")
def accounting_invoice_delete(request, invoice_id: int):
    inv = get_object_or_404(Invoice, pk=invoice_id)
    if inv.payments.exists():
        raise HttpError(400, "This invoice has payments recorded, so it can't be deleted. Issue a credit note instead.")
    inv.delete()
    return {"ok": True}


class PaymentIn(Schema):
    amount: float = Field(..., gt=0, le=100_000_000)
    mode: Literal["UPI", "BANK", "CASH", "CARD"]
    reference_id: str = Field("", max_length=80)
    paid_on: date | None = None
    notes: str = Field("", max_length=200)


@staff_router.post("/accounting/invoices/{invoice_id}/payments")
@needs("accounting.edit")
def accounting_payment(request, invoice_id: int, payload: PaymentIn):
    get_object_or_404(Invoice, pk=invoice_id)
    try:
        acc.record_payment(invoice_id, str(payload.amount), payload.mode, request.auth, reference_id=payload.reference_id,
                           paid_on=payload.paid_on, notes=payload.notes)
    except acc.AccountingError as e:
        bad(e)
    return invoice_payload(Invoice.objects.prefetch_related("lines").get(pk=invoice_id), detail=True)


class ExpenseQuery(Schema):
    start: date | None = None
    end: date | None = None
    category: str | None = Field(None, max_length=14)
    page: int = Field(1, ge=1, le=5000)


def expense_payload(e):
    return {"id": e.pk, "category": e.category, "category_label": e.get_category_display(), "amount": e.amount,
            "gst_amount": e.gst_amount, "vendor": e.vendor, "vendor_gstin": e.vendor_gstin, "spent_on": e.spent_on,
            "description": e.description, "has_receipt": bool(e.receipt), "by": person(e.recorded_by)}


@staff_router.get("/accounting/expenses")
@needs("accounting.view")
def accounting_expenses(request, f: Query[ExpenseQuery]):
    start, end = _range(f.start, f.end)
    qs = Expense.objects.filter(spent_on__range=(start, end)).select_related("recorded_by")
    if f.category:
        qs = qs.filter(category=f.category)
    rows, has_next = page_of(qs, f.page)
    return {"expenses": [expense_payload(e) for e in rows], "has_next": has_next, "page": f.page,
            "categories": [{"key": c.value, "label": c.label} for c in Expense.Category]}


class ExpenseIn(Schema):
    category: Literal[tuple(c.value for c in Expense.Category)]  # type: ignore[valid-type]
    amount: float = Field(..., gt=0, le=100_000_000)
    gst_amount: float = Field(0, ge=0, le=100_000_000)
    vendor: str = Field(..., min_length=1, max_length=140)
    vendor_gstin: str = Field("", max_length=15, pattern=r"^$|^[0-9A-Z]{15}$")
    spent_on: date | None = None
    description: str = Field("", max_length=240)


@staff_router.post("/accounting/expenses")
@needs("accounting.edit")
def accounting_expense_create(request, payload: Form[ExpenseIn], receipt: UploadedFile = File(None)):
    from decimal import Decimal

    if payload.gst_amount > payload.amount:
        raise HttpError(400, "GST can't be more than the total amount.")
    if receipt is not None:
        try:
            V.run(V.RECEIPT, receipt)
        except ValidationError as e:
            bad(e)
    e = Expense.objects.create(
        category=payload.category, amount=Decimal(str(payload.amount)), gst_amount=Decimal(str(payload.gst_amount)),
        vendor=payload.vendor, vendor_gstin=payload.vendor_gstin, spent_on=payload.spent_on or timezone.localdate(),
        description=payload.description, receipt=receipt, recorded_by=request.auth)
    return expense_payload(e)


@staff_router.delete("/accounting/expenses/{expense_id}")
@needs("accounting.edit")
def accounting_expense_delete(request, expense_id: int):
    e = get_object_or_404(Expense, pk=expense_id)
    if e.receipt:
        e.receipt.delete(save=False)
    e.delete()
    return {"ok": True}


@staff_router.get("/accounting/expenses/{expense_id}/receipt")
@needs("accounting.view")
def accounting_receipt(request, expense_id: int):
    e = get_object_or_404(Expense, pk=expense_id)
    if not e.receipt:
        raise Http404
    resp = FileResponse(e.receipt.open("rb"), as_attachment=True, filename=e.receipt.name.rsplit("/", 1)[-1])
    resp["X-Content-Type-Options"] = "nosniff"
    resp["Content-Security-Policy"] = "default-src 'none'; sandbox"
    resp["Cache-Control"] = "private, no-store"
    return resp


@staff_router.get("/accounting/export/{kind}")
@needs("accounting.export")
def accounting_export(request, kind: Literal["invoices", "payments", "expenses"], f: Query[RangeQuery]):
    return acc.export_csv(kind, *_range(f.start, f.end))


class PickQuery(Schema):
    q: str = Field("", max_length=80)


@staff_router.get("/accounting/pick/products")
@needs("accounting.edit")
def accounting_pick_products(request, f: Query[PickQuery]):
    qs = Product.objects.filter(Q(title__icontains=f.q) | Q(sku__icontains=f.q)).order_by("title")[:12]
    return {"products": [{"id": p.pk, "title": p.title, "sku": p.sku, "retail_price": p.retail_price,
                          "wholesale_price": p.wholesale_price} for p in qs]}


@staff_router.get("/accounting/pick/leads")
@needs("accounting.edit")
def accounting_pick_leads(request, f: Query[PickQuery]):
    qs = LeadInquiry.objects.filter(Q(name__icontains=f.q) | Q(business_name__icontains=f.q) | Q(phone__icontains=f.q))[:12]
    return {"leads": [{"id": lead.pk, "name": lead.business_name or lead.name or lead.phone, "phone": lead.phone, "email": lead.email,
                       "city": lead.city, "buyer_type": lead.buyer_type} for lead in qs]}


# ===========================================================================
# Orders & enquiries
# ===========================================================================
class LeadQuery(Schema):
    status: str | None = Field(None, max_length=10)
    source: str | None = Field(None, max_length=10)
    q: str | None = Field(None, max_length=80)
    page: int = Field(1, ge=1, le=5000)


def lead_payload(lead):
    return {"id": lead.pk, "created_at": lead.created_at, "name": lead.name, "phone": lead.phone, "email": lead.email,
            "business_name": lead.business_name, "buyer_type": lead.get_buyer_type_display(), "city": lead.city,
            "message": lead.message, "product": lead.product.title if lead.product_id else None,
            "variant": lead.variant.value if lead.variant_id else None, "package": lead.package.name if lead.package_id else None,
            "quantity": lead.quantity, "tier": lead.tier, "source": lead.source, "source_label": lead.get_source_display(),
            "status": lead.status, "status_label": lead.get_status_display(), "notes": lead.notes}


@staff_router.get("/inquiries")
@needs("leads.view")
def inquiries(request, f: Query[LeadQuery]):
    qs = LeadInquiry.objects.select_related("product", "variant", "package")
    if f.status:
        qs = qs.filter(status=f.status)
    if f.source:
        qs = qs.filter(source=f.source)
    if f.q:
        qs = qs.filter(Q(name__icontains=f.q) | Q(phone__icontains=f.q) | Q(business_name__icontains=f.q) |
                       Q(city__icontains=f.q) | Q(message__icontains=f.q))
    rows, has_next = page_of(qs, f.page)
    return {"leads": [lead_payload(x) for x in rows], "has_next": has_next, "page": f.page,
            "statuses": [{"key": s.value, "label": s.label} for s in LeadInquiry.Status],
            "counts": dict(LeadInquiry.objects.values_list("status").annotate(n=Count("id")))}


class LeadUpdateIn(Schema):
    status: Literal["new", "contacted", "quoted", "won", "lost"] | None = None
    notes: str | None = Field(None, max_length=4000)


@staff_router.patch("/inquiries/{lead_id}")
@needs("leads.update")
def inquiry_update(request, lead_id: int, payload: LeadUpdateIn):
    lead = get_object_or_404(LeadInquiry.objects.select_related("product", "variant", "package"), pk=lead_id)
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(lead, k, v)
    lead.save()
    return lead_payload(lead)


# ===========================================================================
# Catalog & 3D media
# ===========================================================================
def product3d_payload(p, request=None):
    imgs = getattr(p, "first_images", None)
    return {"id": p.pk, "title": p.title, "sku": p.sku, "slug": p.slug,
            "thumb": spec_url(request, imgs[0].thumb) if imgs else None,
            "model_3d": media_url(request, p.model_3d), "model_size_mb": round(p.model_3d.size / 1048576, 2) if p.model_3d else None,
            "model_poster": media_url(request, p.model_poster), "is_hero_3d_featured": p.is_hero_3d_featured,
            "hero_3d_order": p.hero_3d_order, "is_active": p.is_active}


class CatalogQuery(Schema):
    q: str | None = Field(None, max_length=80)
    has3d: bool | None = None
    page: int = Field(1, ge=1, le=5000)


def _products3d():
    return Product.objects.prefetch_related(Prefetch("images", queryset=ProductImage.objects.order_by("order"), to_attr="first_images"))


@staff_router.get("/catalog/products")
@needs("catalog.media")
def catalog_products(request, f: Query[CatalogQuery]):
    qs = _products3d().order_by("-is_hero_3d_featured", "hero_3d_order", "title")
    if f.q:
        qs = qs.filter(Q(title__icontains=f.q) | Q(sku__icontains=f.q))
    if f.has3d is True:
        qs = qs.exclude(model_3d="")
    elif f.has3d is False:
        qs = qs.filter(model_3d="")
    rows, has_next = page_of(qs, f.page)
    return {"products": [product3d_payload(p, request) for p in rows], "has_next": has_next, "page": f.page,
            "max_mb": settings.MAX_3D_MODEL_MB}


@staff_router.post("/catalog/products/{product_id}/model3d")
@needs("catalog.media")
def catalog_upload_3d(request, product_id: int, model: UploadedFile = File(None), poster: UploadedFile = File(None)):
    p = get_object_or_404(Product, pk=product_id)
    if model is None and poster is None:
        raise HttpError(400, "Choose a .glb model or a poster image to upload.")
    try:
        if model is not None:
            V.run(V.MODEL_3D, model)
        if poster is not None:
            V.run(V.IMAGE, poster)
            forms.ImageField().clean(poster)  # must really be a picture
    except ValidationError as e:
        bad(e)
    if model is not None:
        if p.model_3d:
            p.model_3d.delete(save=False)
        p.model_3d = model
    if poster is not None:
        if p.model_poster:
            p.model_poster.delete(save=False)
        p.model_poster = poster
    p.save()
    return product3d_payload(_products3d().get(pk=p.pk), request)


@staff_router.delete("/catalog/products/{product_id}/model3d")
@needs("catalog.media")
def catalog_remove_3d(request, product_id: int):
    p = get_object_or_404(Product, pk=product_id)
    for f in (p.model_3d, p.model_poster):
        if f:
            f.delete(save=False)
    p.model_3d, p.model_poster, p.is_hero_3d_featured = "", "", False
    p.save()
    return product3d_payload(_products3d().get(pk=p.pk), request)


class Hero3DIn(Schema):
    featured: bool
    order: int = Field(0, ge=0, le=10_000)


@staff_router.patch("/catalog/products/{product_id}/hero3d")
@needs("catalog.media")
def catalog_hero3d(request, product_id: int, payload: Hero3DIn):
    p = get_object_or_404(Product, pk=product_id)
    if payload.featured and not p.model_3d:
        raise HttpError(400, "Upload a 3D model first.")
    p.is_hero_3d_featured, p.hero_3d_order = payload.featured, payload.order
    p.save(update_fields=["is_hero_3d_featured", "hero_3d_order", "updated_at"])
    from storefront.utils import clear_site_cache

    clear_site_cache()
    return product3d_payload(_products3d().get(pk=p.pk), request)


# ===========================================================================
# Traffic analytics
# ===========================================================================
class TrackIn(Schema):
    path: str = Field(..., max_length=300)
    referrer: str = Field("", max_length=300)
    tier: Literal["retail", "wholesale"] = "retail"
    sid: str = Field("", max_length=64)
    category: str = Field("", max_length=100)


@analytics_router.post("/track")
@rate_limit("track", lambda: settings.RATE_LIMIT_TRACK_PER_MIN)
def track(request, payload: TrackIn):
    analytics.record(request, path=payload.path, referrer=payload.referrer, tier=payload.tier, sid=payload.sid,
                     category=payload.category)
    return {"ok": True}


@staff_router.get("/analytics/summary")
@needs("analytics.view")
def analytics_summary(request, period: Literal["24h", "7d", "30d"] = "7d"):
    return analytics.summary(period)


# ===========================================================================
# Team (super admin only)
# ===========================================================================
def staff_payload(u):
    prof = getattr(u, "staff_profile", None)
    role = user_role(u)
    return {"id": u.pk, "username": u.get_username(), "name": u.get_full_name(), "email": u.email,
            "role": (Role.SUPER_ADMIN if u.is_superuser else prof.role) if (u.is_superuser or prof) else None,
            "role_label": role.label if role else "No access", "active": bool(role), "last_login": u.last_login}


@staff_router.get("/team")
@needs("staff.manage")
def team(request):
    users = User.objects.filter(Q(is_superuser=True) | Q(staff_profile__isnull=False)).select_related("staff_profile").order_by("username")
    return {"people": [staff_payload(u) for u in users], "roles": [{"key": r.value, "label": r.label} for r in Role]}


class StaffIn(Schema):
    username: str = Field(..., min_length=3, max_length=150, pattern=r"^[\w.@+-]+$")
    first_name: str = Field("", max_length=150)
    email: str = Field("", max_length=254)
    role: Literal[tuple(r.value for r in Role)]  # type: ignore[valid-type]


def _temp_password():
    return secrets.token_urlsafe(9)


@staff_router.post("/team")
@needs("staff.manage")
def team_add(request, payload: StaffIn):
    if User.objects.filter(username__iexact=payload.username).exists():
        raise HttpError(400, "That username is taken.")
    password = _temp_password()
    with transaction.atomic():
        u = User.objects.create_user(username=payload.username, email=payload.email, password=password, first_name=payload.first_name)
        StaffProfile.objects.create(user=u, role=payload.role)
    return {"person": staff_payload(User.objects.select_related("staff_profile").get(pk=u.pk)), "temporary_password": password}


class StaffEditIn(Schema):
    role: Literal[tuple(r.value for r in Role)] | None = None  # type: ignore[valid-type]
    active: bool | None = None


@staff_router.patch("/team/{user_id}")
@needs("staff.manage")
def team_edit(request, user_id: int, payload: StaffEditIn):
    u = get_object_or_404(User, pk=user_id)
    if u.pk == request.auth.pk:
        raise HttpError(400, "You can't change your own role or access.")
    prof, _ = StaffProfile.objects.get_or_create(user=u, defaults={"role": Role.SUPER_ADMIN if u.is_superuser else Role.EMPLOYEE_OPS})
    if payload.role is not None:
        prof.role = payload.role
    if payload.active is not None:
        prof.is_active = payload.active
        if not payload.active and u.is_superuser:
            prof.role = Role.EMPLOYEE_OPS  # removing access also removes super admin rights
    try:
        prof.full_clean()
    except ValidationError as e:
        bad(e)
    prof.save()
    return staff_payload(User.objects.select_related("staff_profile").get(pk=u.pk))


@staff_router.post("/team/{user_id}/reset-password")
@needs("staff.manage")
def team_reset(request, user_id: int):
    u = get_object_or_404(User, pk=user_id)
    if u.pk == request.auth.pk:
        raise HttpError(400, "Use 'Change password' in the admin for your own account.")
    password = _temp_password()
    u.set_password(password)
    u.save(update_fields=["password"])
    return {"temporary_password": password}
