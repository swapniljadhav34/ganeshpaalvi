"""
Turn database rows into lightweight JSON for the website.

Plain functions (not heavy serializer classes) keep the catalog API fast even with
50,000+ products. Product cards only carry what a card shows; the detail endpoint
adds everything else.
"""

from django.conf import settings

from catalog.models import Ingredient, Product
from storefront import design as D
from storefront.models import (
    ActiveTheme,
    AIAssistantConfig,
    BrandSettings,
    FooterColumn,
    HeroSlide,
    NavLink,
    PageSection,
    SiteDesign,
)


def media_url(request, file_field):
    """Absolute URL for an uploaded file (local disk or S3/R2).

    Built from settings.MEDIA_BASE_URL — never from the request's Host header — because these URLs
    are cached and shared with every visitor (a request via 127.0.0.1 must not poison them).
    """
    if not file_field:
        return None
    try:
        url = file_field.url
    except (ValueError, OSError):
        return None
    if url.startswith("http"):
        return url
    return f"{settings.MEDIA_BASE_URL}{url}"


def spec_url(request, spec):
    """URL of an auto-generated thumbnail; falls back gracefully if generation fails."""
    try:
        return media_url(request, spec)
    except Exception:  # missing/corrupt source image shouldn't break the catalog
        return None


def money(value):
    return float(value) if value is not None else None


# --- Products ---------------------------------------------------------------
def product_card(request, p: Product):
    images = list(p.images.all())[:2]
    variants = list(p.variants.all())
    return {
        "id": p.pk,
        "slug": p.slug,
        "title": p.title,
        "subtitle": p.subtitle,
        "sku": p.sku,
        "category": {"name": p.category.name, "slug": p.category.slug} if p.category_id else None,
        "images": [
            {"thumb": spec_url(request, im.thumb), "medium": spec_url(request, im.medium), "alt": im.alt_text or p.title}
            for im in images
        ],
        "mrp": money(p.mrp),
        "retail_price": money(p.retail_price),
        "wholesale_price": money(p.wholesale_price),
        "moq": p.moq,
        "discount_percent": p.discount_percent,
        "net_quantity": money(p.net_quantity),
        "unit": p.unit,
        "stock_status": p.stock_status,
        "is_featured": p.is_featured,
        "is_new_arrival": p.is_new_arrival,
        "is_bestseller": p.is_bestseller,
        "badges": [{"name": b.name, "slug": b.slug} for b in p.badges.all()],
        "swatches": [
            {"type": v.variant_type, "value": v.value, "hex": v.swatch_hex or None}
            for v in variants if v.variant_type in ("colour", "bristle", "flavour")
        ][:6],
        "packages": [{"name": pk.name, "units": pk.units_per_pack} for pk in p.packages.all()][:4],
    }


def product_detail(request, p: Product):
    data = product_card(request, p)
    data.update({
        "images": [
            {
                "thumb": spec_url(request, im.thumb),
                "medium": spec_url(request, im.medium),
                "full": media_url(request, im.image),
                "alt": im.alt_text or p.title,
            }
            for im in p.images.all()
        ],
        "ean": p.ean,
        "description": p.description,
        "key_benefits": p.key_benefits or [],
        "how_to_use": [line.strip() for line in (p.how_to_use or "").splitlines() if line.strip()],
        "ingredients_text": p.ingredients_text,
        "key_ingredients": [
            {"name": i.name, "icon": i.icon, "benefit": i.short_benefit, "image": media_url(request, i.image)}
            for i in p.key_ingredients.all()
        ],
        "badges": [{"name": b.name, "slug": b.slug, "icon": b.icon, "description": b.description} for b in p.badges.all()],
        "suitable_for": p.suitable_for or [],
        "demo_video": media_url(request, p.demo_video),
        "model_3d": media_url(request, p.model_3d),
        "model_poster": media_url(request, p.model_poster),
        "shelf_life": p.shelf_life,
        "country_of_origin": p.country_of_origin,
        "variants": [
            {
                "id": v.pk, "type": v.variant_type, "type_label": v.get_variant_type_display(), "value": v.value,
                "sku": v.sku, "hex": v.swatch_hex or None, "image": media_url(request, v.image),
                "price_override": money(v.price_override), "stock_status": v.stock_status,
            }
            for v in p.variants.all()
        ],
        "packages": [
            {
                "id": pk.pk, "name": pk.name, "units": pk.units_per_pack,
                "retail_price": money(pk.retail_price) if pk.retail_price is not None
                else money(p.retail_price * pk.units_per_pack),
                "wholesale_price": money(pk.wholesale_price) if pk.wholesale_price is not None
                else (money(p.wholesale_price * pk.units_per_pack) if p.wholesale_price else None),
                "moq": pk.moq,
            }
            for pk in p.packages.all()
        ],
        "seo_title": p.seo_title or p.title,
        "seo_description": p.seo_description or (p.subtitle or p.description[:155]),
        "url": p.get_absolute_url(),
        "updated_at": p.updated_at.isoformat(),
    })
    return data


# --- Homepage bootstrap -----------------------------------------------------
def brand_payload(request, b: BrandSettings):
    return {
        "name": b.brand_name,
        "tagline": b.tagline,
        "logo_light": media_url(request, b.logo_light),
        "logo_dark": media_url(request, b.logo_dark),
        "favicon": media_url(request, b.favicon),
        "email": b.contact_email,
        "whatsapp": "".join(ch for ch in b.whatsapp_number if ch.isdigit()),
        "phone": b.phone,
        "instagram": b.instagram_url,
        "facebook": b.facebook_url,
        "x": b.x_url,
        "address": b.registered_address,
        "maps": b.google_maps_link,
        "gstin": b.gstin,
        "manufacturer": b.manufacturer_details,
        "marketer": b.marketer_details,
        "customer_care": b.customer_care_details,
        "announcement": {
            "text": b.announcement_text, "link": b.announcement_link,
            "active": b.announcement_active and bool(b.announcement_text),
            "messages": [m for m in [b.announcement_text, *b.announcement_more.splitlines()] if m.strip()],
        },
        "footer_story": b.footer_story,
        "privacy_policy": b.privacy_policy,
        "seo": {"title": b.default_seo_title, "description": b.default_seo_description, "image": media_url(request, b.og_share_image)},
        "site_url": settings.SITE_URL,
    }


def theme_payload():
    at = ActiveTheme.load()
    preset, why = at.resolve()
    tokens = preset.as_tokens() if preset else None
    return {"tokens": tokens, "source": why, "ambient_enabled": at.enable_ambient_effects}


def srcset(request, small, large):
    """'<800w url> 800w, <1600w url> 1600w' so phones download a phone-sized picture."""
    parts = [(spec_url(request, small), 800), (spec_url(request, large), 1600)]
    out = ", ".join(f"{u} {w}w" for u, w in parts if u)
    return out or None


def media_list(request, main_image=None, main_video=None, main_video_mobile=None, items=(), *, main_alt="", main_specs=None):
    """Main picture/video first, then the extra gallery items — one simple list for the website."""
    out = []
    poster = media_url(request, main_image)
    main_srcset = srcset(request, *main_specs) if (main_specs and main_image) else None
    video = media_url(request, main_video)
    if video or main_video_mobile:
        out.append({"type": "video", "src": video or media_url(request, main_video_mobile),
                    "src_mobile": media_url(request, main_video_mobile), "poster": poster, "caption": "", "link": "", "alt": main_alt})
    elif poster:
        out.append({"type": "image", "src": poster, "srcset": main_srcset, "caption": "", "link": "", "alt": main_alt})
    for m in items:
        img, vid = media_url(request, m.image), media_url(request, m.video)
        if not (img or vid):
            continue
        out.append({"type": "video" if vid else "image", "src": vid or img, "poster": img if vid else None,
                    "srcset": None if vid or not m.image else srcset(request, m.img_800, m.img_1600),
                    "caption": m.caption, "link": m.link, "alt": m.alt_text or m.caption})
    return out


def hero_slide_payload(request, h, fallback_product=None):
    product = h.product if (h.product_id and h.product.is_active) else fallback_product
    return {
        "id": h.pk, "layout": h.layout, "eyebrow": h.eyebrow, "headline": h.headline, "subheadline": h.subheadline,
        "headline_size": h.headline_size, "text_tone": h.text_tone, "overlay_strength": h.overlay_strength, "height": h.height,
        "video_desktop": media_url(request, h.video_desktop), "video_mobile": media_url(request, h.video_mobile),
        "poster": media_url(request, h.poster_image),
        "media": media_list(request, h.poster_image, h.video_desktop, h.video_mobile, h.media.all(), main_alt=h.media_alt,
                            main_specs=(h.poster_800, h.poster_1600)),
        "cta_text": h.cta_text, "cta_link": h.cta_link,
        "secondary_cta_text": h.secondary_cta_text, "secondary_cta_link": h.secondary_cta_link,
        "show_product": h.show_product, "product": product_card(request, product) if (product and h.show_product) else None,
        **h.design_payload(),
    }


def _hero_fallback_product():
    return Product.objects.live().filter(is_featured=True).for_cards().order_by("order").first()


def hero_payload(request):
    slides = list(HeroSlide.objects.filter(HeroSlide.live_q())
                  .select_related("product__category").prefetch_related("media"))
    fallback = _hero_fallback_product() if any(h.show_product and not h.product_id for h in slides) else None
    return [hero_slide_payload(request, h, fallback) for h in slides]


def _mini_products(request, slugs):
    """Resolve product slugs mentioned in section items into small cards (one query)."""
    slugs = [s for s in slugs if s]
    if not slugs:
        return {}
    qs = Product.objects.live().filter(slug__in=slugs).for_cards()
    return {p.slug: product_card(request, p) for p in qs}


def _section_slugs(section):
    """Product slugs mentioned inside a section's items (routine steps, guide rows…)."""
    items = section.items or []
    rows = [st for steps in items.values() for st in (steps or [])] if isinstance(items, dict) else items
    return [r.get("product") for r in rows if isinstance(r, dict) and r.get("product")]


def sections_payload(request, sections=None):
    out = []
    if sections is None:
        sections = list(PageSection.objects.filter(PageSection.live_q()).select_related("category").prefetch_related("media"))

    # Collect every product slug referenced by routine/guide items so we fetch them once.
    per_section = {sec.pk: _section_slugs(sec) for sec in sections}
    referenced = [slug for slugs in per_section.values() for slug in slugs]
    minis = _mini_products(request, referenced)
    hero_product = None
    if any(s.section_type == PageSection.SectionType.HERO_BANNER for s in sections):
        hero_product = _hero_fallback_product()

    for s in sections:
        data = {
            "id": s.pk, "type": s.section_type, "eyebrow": s.eyebrow, "title": s.title, "body": s.body,
            "image": media_url(request, s.image), "video": media_url(request, s.video),
            "media": media_list(request, s.image, s.video, None, s.media.all(), main_alt=s.media_alt,
                                main_specs=(s.img_800, s.img_1600)),
            "cta_text": s.cta_text, "cta_link": s.cta_link, "background": s.background_style,
            "hero_layout": s.hero_layout, "media_position": s.media_position,
            "items": s.items or [],
            **s.design_payload(),
        }
        if s.section_type == PageSection.SectionType.HERO_BANNER and hero_product:
            data["product"] = product_card(request, hero_product)
        if s.section_type == PageSection.SectionType.FEATURED_COLLECTION:
            qs = Product.objects.live()
            qs = qs.filter(category_id__in=s.category.descendant_ids()) if s.category_id else qs.filter(is_featured=True)
            data["products"] = [product_card(request, p) for p in qs.for_cards().order_by("order", "-created_at")[:12]]
            data["category"] = s.category.slug if s.category_id else None
        if s.section_type == PageSection.SectionType.INGREDIENT_SPOTLIGHT and not s.items:
            data["items"] = [
                {"name": i.name, "benefit": i.short_benefit, "icon": i.icon, "image": media_url(request, i.image)}
                for i in Ingredient.objects.filter(is_spotlight=True)[:8]
            ]
        # Only the products this section's steps/rows point at.
        data["linked_products"] = {slug: minis[slug] for slug in per_section[s.pk] if slug in minis}
        out.append(data)
    return out


def design_payload():
    return SiteDesign.load().payload()


def nav_payload():
    return [{"label": n.label, "link": n.link, "highlight": n.highlight} for n in NavLink.objects.filter(is_active=True)]


def footer_payload():
    return [
        {"title": c.title, "kind": c.kind, "links": [{"label": l.label, "link": l.link, "icon": l.icon} for l in c.links.all()]}
        for c in FooterColumn.objects.filter(is_active=True).prefetch_related("links")
    ]


def fx_payload():
    return D.registry_payload()


def hero_3d_payload(request):
    """Products the owner picked for the homepage 3D showcase, in their chosen order."""
    qs = (Product.objects.live().filter(is_hero_3d_featured=True).exclude(model_3d="")
          .for_cards().order_by("hero_3d_order", "order")[:8])
    out = []
    for p in qs:
        card = product_card(request, p)
        card["model_3d"] = media_url(request, p.model_3d)
        card["model_poster"] = media_url(request, p.model_poster) or (card["images"][0]["medium"] if card["images"] else None)
        out.append(card)
    return out


def ai_payload():
    cfg = AIAssistantConfig.load()
    return {
        "active": cfg.is_active,
        "name": cfg.assistant_name,
        "greeting": cfg.welcome_greeting,
        "prompts": cfg.quick_prompts or [],
    }
