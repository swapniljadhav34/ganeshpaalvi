"""Numbers for the admin dashboard home page (wired up via UNFOLD['DASHBOARD_CALLBACK'])."""

from datetime import timedelta

from django.conf import settings
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product
from leads.models import LeadInquiry

from .models import ActiveTheme


def dashboard_callback(request, context):
    now = timezone.localtime()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    products = Product.objects
    total = products.count()
    active = products.filter(is_active=True).count()
    low_qs = products.filter(stock_status__in=[Product.StockStatus.LOW, Product.StockStatus.OUT]).order_by("stock_status", "title")
    leads = LeadInquiry.objects
    leads_today = leads.filter(created_at__gte=today).count()
    leads_week = leads.filter(created_at__gte=week_ago).count()
    new_open = leads.filter(status=LeadInquiry.Status.NEW).count()

    month = leads.filter(created_at__gte=month_ago)
    by_buyer_raw = dict(month.values_list("buyer_type").annotate(n=Count("id")))
    labels = dict(LeadInquiry.BuyerType.choices)
    retail = by_buyer_raw.get(LeadInquiry.BuyerType.SHOPPER, 0)
    b2b = sum(n for k, n in by_buyer_raw.items() if k != LeadInquiry.BuyerType.SHOPPER)

    at = ActiveTheme.load()
    preset, why = at.resolve()
    next_fest = at.festivals.filter(is_active=True, start_date__gt=now.date()).select_related("preset").first()

    product_url = reverse("admin:catalog_product_changelist")
    lead_url = reverse("admin:leads_leadinquiry_changelist")
    context["dash"] = {
        "site_url": settings.SITE_URL,
        "kpis": [
            {"label": "Products live", "value": f"{active:,}", "hint": f"of {total:,} total", "link": f"{product_url}?is_active__exact=1"},
            {"label": "Low / out of stock", "value": low_qs.count(), "hint": "needs attention", "link": f"{product_url}?stock_status__exact=low"},
            {"label": "New leads today", "value": leads_today, "hint": f"{leads_week} this week", "link": f"{lead_url}?status__exact=new"},
            {"label": "Waiting for reply", "value": new_open, "hint": "status: New", "link": f"{lead_url}?status__exact=new"},
        ],
        "top_products": list(
            month.exclude(product=None).values("product__id", "product__title").annotate(n=Count("id")).order_by("-n")[:6]
        ),
        "split": {"b2b": b2b, "retail": retail, "b2b_pct": round(100 * b2b / (b2b + retail)) if (b2b + retail) else 0},
        "by_buyer": [{"label": labels.get(k, k), "n": n} for k, n in sorted(by_buyer_raw.items(), key=lambda kv: -kv[1])],
        "low_stock": list(low_qs[:8]),
        "theme": preset,
        "theme_colors": [preset.surface, preset.primary, preset.secondary, preset.accent, preset.text] if preset else [],
        "theme_reason": {"manual": "Manual override", "festival": "Festival schedule", "default": "Everyday theme",
                         "fallback": "First preset"}.get(why, ""),
        "next_festival": f"{next_fest} — from {next_fest.start_date:%d %b}" if next_fest else "",
    }
    return context
