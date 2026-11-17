"""
Paalvi public API (Django Ninja) — mounted at /api/.

  GET  /api/bootstrap          everything the homepage needs (cached 5 min, auto-cleared on admin save)
  GET  /api/products           paginated catalog with filters
  GET  /api/products/{slug}    full product detail + related + "complete your routine"
  POST /api/ai-guide           AI Care Guide (RAG over the catalog)
  POST /api/inquiry            lead capture (WhatsApp taps, forms, B2B requests)
"""

import logging
from typing import Literal

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db.models import Q
from django.shortcuts import get_object_or_404
from ninja import NinjaAPI, Query, Schema
from ninja.errors import HttpError
from pydantic import EmailStr, Field, field_validator

from catalog.models import Badge, Category, PackageOption, Product, ProductVariant
from leads.models import LeadInquiry
from storefront.models import BrandSettings
from storefront.utils import BOOTSTRAP_CACHE_KEY

from . import serializers as s
from .ai import ask_guide
from .ratelimit import rate_limit
from .search import filter_products

log = logging.getLogger("paalvi")
api = NinjaAPI(title="Paalvi API", version="1.0", docs_url="/docs" if settings.DEBUG else None)
PAGE_SIZE = 24

# Steps of a daily oral-care routine, matched against category names/slugs.
ROUTINE_STEPS = [
    ("brush", ["brush"]),
    ("paste", ["paste", "toothpaste", "gel"]),
    ("floss", ["floss", "interdental"]),
    ("tongue", ["tongue"]),
    ("rinse", ["mouthwash", "rinse"]),
]


# --- Bootstrap --------------------------------------------------------------
def categories_tree():
    cats = list(Category.objects.filter(is_active=True).order_by("order", "name"))
    nodes = {c.pk: {"id": c.pk, "name": c.name, "slug": c.slug, "description": c.description, "icon": c.icon,
                    "image": None, "_img": c.image, "parent": c.parent_id, "children": []} for c in cats}
    roots = []
    for n in nodes.values():
        (nodes[n["parent"]]["children"] if n["parent"] in nodes else roots).append(n)
    return roots, nodes


@api.get("/bootstrap", tags=["site"])
def bootstrap(request):
    data = cache.get(BOOTSTRAP_CACHE_KEY)
    if data is None:
        roots, nodes = categories_tree()
        for n in nodes.values():
            n["image"] = s.media_url(request, n.pop("_img"))
        data = {
            "brand": s.brand_payload(request, BrandSettings.load()),
            "theme": s.theme_payload(),
            "hero": s.hero_payload(request),
            "sections": s.sections_payload(request),
            "categories": roots,
            "badges": [{"name": b.name, "slug": b.slug, "icon": b.icon, "description": b.description} for b in Badge.objects.all()],
            "filters": {
                "suitable_for": [{"value": v, "label": l} for v, l in Product.SUITABLE_CHOICES],
                "variants": [
                    {"type": t, "label": label, "values": sorted(set(
                        ProductVariant.objects.filter(variant_type=t, product__is_active=True).values_list("value", flat=True)
                    ))[:20]}
                    for t, label in [("bristle", "Bristle"), ("flavour", "Flavour")]
                ],
            },
            "ai": s.ai_payload(),
            "design": s.design_payload(),
            "nav": s.nav_payload(),
            "footer": s.footer_payload(),
            "fx": s.fx_payload(),
        }
        cache.set(BOOTSTRAP_CACHE_KEY, data, 300)
    return data


@api.get("/preview", tags=["site"], include_in_schema=False)
def preview(request, token: str):
    """Admin live preview: a hero slide or section by id, even while hidden (needs a signed admin token)."""
    from django.core import signing

    from storefront.models import HeroSlide, PageSection
    from storefront.preview import read_token

    try:
        kind, pk = read_token(token)
    except signing.BadSignature:
        raise HttpError(403, "This preview link has expired. Reload the admin page.")
    item = None
    if kind == "hero" and pk:
        h = HeroSlide.objects.filter(pk=pk).select_related("product").prefetch_related("media").first()
        item = s.hero_slide_payload(request, h, s._hero_fallback_product()) if h else None
    elif kind == "section" and pk:
        sec = PageSection.objects.filter(pk=pk).select_related("category").prefetch_related("media").first()
        item = s.sections_payload(request, [sec])[0] if sec else None
    return {"kind": kind, "item": item}


# --- Catalog ----------------------------------------------------------------
class ProductFilters(Schema):
    q: str | None = None
    category: str | None = None
    badge: str | None = None
    suitable_for: str | None = None
    variant: str | None = Field(None, description="e.g. bristle:soft or flavour:mint (comma separated)")
    sort: Literal["newest", "price_asc", "price_desc", "discount", "bestseller", "featured"] | None = None
    min_discount: int | None = Field(None, ge=0, le=90)
    min_price: float | None = None
    max_price: float | None = None
    featured: bool | None = None
    tier: Literal["retail", "wholesale"] | None = None
    page: int = Field(1, ge=1, le=5000)


@api.get("/products", tags=["catalog"])
def products(request, f: Query[ProductFilters]):
    qs = filter_products(
        Product.objects.live(), q=f.q, category=f.category, badge=f.badge, suitable_for=f.suitable_for,
        variant=f.variant, min_discount=f.min_discount, featured=f.featured, tier=f.tier,
        min_price=f.min_price, max_price=f.max_price, sort=f.sort,
    )
    start = (f.page - 1) * PAGE_SIZE
    # Fetch one extra row to know if there's another page without a slow COUNT on huge catalogs.
    rows = list(qs.for_cards()[start : start + PAGE_SIZE + 1])
    has_next = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]
    total = qs.count() if f.page == 1 else None
    return {"items": [s.product_card(request, p) for p in rows], "page": f.page, "has_next": has_next, "total": total}


def routine_step(category):
    hay = f"{category.slug} {category.name}".lower()
    for i, (_, words) in enumerate(ROUTINE_STEPS):
        if any(w in hay for w in words):
            return i
    return None


@api.get("/products/{slug}", tags=["catalog"])
def product_detail(request, slug: str):
    p = get_object_or_404(
        Product.objects.live().select_related("category").prefetch_related(
            "images", "badges", "key_ingredients", "variants", "packages"),
        slug=slug,
    )
    data = s.product_detail(request, p)

    # Related: same category first, topped up from the parent category family.
    family = p.category.parent.descendant_ids() if p.category.parent_id else p.category.descendant_ids()
    related = list(Product.objects.live().filter(category_id__in=family).exclude(pk=p.pk)
                   .for_cards().order_by("-is_bestseller", "order", "-created_at")[:24])
    related.sort(key=lambda r: r.category_id != p.category_id)  # stable: same-category items first
    data["related"] = [s.product_card(request, r) for r in related[:8]]

    # "Complete your routine": one top product from each other routine step (brush → paste → floss → rinse).
    my_step = routine_step(p.category)
    routine = []
    for i, (step, words) in enumerate(ROUTINE_STEPS):
        if i == my_step:
            continue
        cond = Q()
        for w in words:
            cond |= Q(category__name__icontains=w) | Q(category__slug__icontains=w)
        pick = (Product.objects.live().filter(cond).exclude(pk=p.pk).for_cards()
                .order_by("-is_bestseller", "-is_featured", "order").first())
        if pick:
            routine.append({"step": step, "product": s.product_card(request, pick)})
    data["routine"] = routine[:4]
    return data


# --- AI Care Guide ----------------------------------------------------------
class ChatTurn(Schema):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=2000)


class GuideIn(Schema):
    message: str = Field(..., min_length=1, max_length=1000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)
    tier: Literal["retail", "wholesale"] = "retail"


@api.post("/ai-guide", tags=["ai"])
@rate_limit("ai", lambda: settings.RATE_LIMIT_AI_PER_MIN)
def ai_guide(request, payload: GuideIn):
    from storefront.models import AIAssistantConfig

    if not AIAssistantConfig.load().is_active:
        raise HttpError(503, "The Care Guide is resting right now. Please reach us on WhatsApp.")
    return ask_guide(request, payload.message.strip(), [t.dict() for t in payload.history], payload.tier)


# --- Leads ------------------------------------------------------------------
class InquiryIn(Schema):
    name: str = Field("", max_length=100)
    phone: str = Field("", max_length=20)
    email: EmailStr | None = None
    business_name: str = Field("", max_length=140)
    buyer_type: Literal["shopper", "retailer", "chemist", "hotel", "salon", "corporate", "distributor"] = "shopper"
    city: str = Field("", max_length=80)
    message: str = Field("", max_length=2000)
    product: str | None = Field(None, description="Product slug")
    variant_id: int | None = None
    package_id: int | None = None
    tier: Literal["retail", "wholesale"] = "retail"
    quantity: int | None = Field(None, ge=1, le=10_000_000)
    source: Literal["whatsapp", "email", "ai", "contact", "b2b"] = "contact"
    page_url: str = Field("", max_length=400)
    website: str = Field("", description="Honeypot — real people leave this empty.")

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, v):
        v = (v or "").strip()
        digits = "".join(ch for ch in v if ch.isdigit())
        if v and not (10 <= len(digits) <= 13):
            raise ValueError("Please enter a valid mobile number (10 digits).")
        return ("+" + digits) if v.startswith("+") else digits


@api.post("/inquiry", tags=["leads"])
@rate_limit("inquiry", lambda: settings.RATE_LIMIT_INQUIRY_PER_MIN)
def inquiry(request, payload: InquiryIn):
    if payload.website:  # a bot filled the hidden field — pretend success, save nothing
        return {"ok": True}
    needs_contact = payload.source not in ("whatsapp",)  # WhatsApp taps identify themselves inside WhatsApp
    if needs_contact and not (payload.phone or payload.email):
        raise HttpError(422, "Please share a phone number or email so we can get back to you.")

    product = Product.objects.filter(slug=payload.product).first() if payload.product else None
    variant = ProductVariant.objects.filter(pk=payload.variant_id, product=product).first() if (product and payload.variant_id) else None
    package = PackageOption.objects.filter(pk=payload.package_id, product=product).first() if (product and payload.package_id) else None

    lead = LeadInquiry.objects.create(
        name=payload.name.strip(), phone=payload.phone, email=payload.email or "", business_name=payload.business_name.strip(),
        buyer_type=payload.buyer_type, city=payload.city.strip(), message=payload.message.strip(), product=product,
        variant=variant, package=package, tier=payload.tier, quantity=payload.quantity, source=payload.source,
        page_url=payload.page_url,
    )
    if settings.LEAD_NOTIFY_EMAILS and payload.source != "whatsapp":
        try:
            send_mail(
                subject=f"New Paalvi lead: {lead}",
                message=(f"{lead.get_buyer_type_display()} · {lead.city}\nPhone: {lead.phone}\nEmail: {lead.email}\n"
                         f"Product: {product or '—'} · Qty: {lead.quantity or '—'} · {lead.get_tier_display()}\n\n{lead.message}"),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=settings.LEAD_NOTIFY_EMAILS,
                fail_silently=True,
            )
        except Exception as exc:
            log.warning("Lead email failed: %s", exc)
    return {"ok": True, "id": lead.pk}
