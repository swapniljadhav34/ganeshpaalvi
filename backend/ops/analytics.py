"""
First-party traffic analytics. Privacy by design:
  • no cookies; the browser sends a random tab id that we hash with a salt that changes daily,
    so a visitor can't be followed across days,
  • no IP addresses or full user agents are stored,
  • bots are ignored, and rows older than TRAFFIC_RETENTION_DAYS are deleted nightly.
"""

import hashlib
import re
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.db.models import Count
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone

from catalog.models import Product

from .models import TrafficEvent

BOT_RE = re.compile(r"bot|crawl|spider|slurp|facebookexternalhit|whatsapp|preview|headless|lighthouse|pingdom|monitor", re.I)
PRODUCT_PATH = re.compile(r"^/p/([a-z0-9\-]+)/?$")
PERIODS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}


def device_of(ua):
    if re.search(r"iPad|Tablet|PlayBook|Silk|(Android(?!.*Mobile))", ua or ""):
        return TrafficEvent.Device.TABLET
    if re.search(r"Mobi|iPhone|iPod|Android.*Mobile|Opera Mini|IEMobile", ua or ""):
        return TrafficEvent.Device.MOBILE
    return TrafficEvent.Device.DESKTOP


def session_hash(sid, request):
    today = timezone.localdate().isoformat()
    seed = sid or f"{request.META.get('REMOTE_ADDR', '')}|{request.META.get('HTTP_USER_AGENT', '')}"
    return hashlib.sha256(f"{settings.SECRET_KEY}|{today}|{seed}".encode()).hexdigest()[:16]


def referrer_host(ref, request):
    host = (urlparse(ref or "").hostname or "").lower()
    own = request.get_host().split(":")[0].lower()
    return "" if not host or host == own or host.endswith("." + own) else host[:120]


def record(request, *, path, referrer="", tier="retail", sid="", category=""):
    ua = request.META.get("HTTP_USER_AGENT", "")
    if not ua or BOT_RE.search(ua):
        return None
    path = (urlparse(path or "/").path or "/")[:200]
    product = None
    m = PRODUCT_PATH.match(path)
    if m:
        product = Product.objects.filter(slug=m.group(1)).only("pk").first()
    return TrafficEvent.objects.create(
        kind=TrafficEvent.Kind.PRODUCT if product else TrafficEvent.Kind.PAGEVIEW,
        path=path, product=product, category_slug=(category or "")[:100], referrer_host=referrer_host(referrer, request),
        device=device_of(ua), tier="wholesale" if tier == "wholesale" else "retail", session_hash=session_hash(sid, request),
    )


def summary(period="7d"):
    delta = PERIODS.get(period, PERIODS["7d"])
    since = timezone.now() - delta
    qs = TrafficEvent.objects.filter(created_at__gte=since)
    total = qs.count()
    sessions = qs.values("session_hash").distinct().count()

    def split(field):
        return {r[field]: r["n"] for r in qs.values(field).annotate(n=Count("id"))}

    trunc = TruncHour("created_at") if period == "24h" else TruncDate("created_at")
    trend = [
        {"t": (r["t"].isoformat() if hasattr(r["t"], "isoformat") else str(r["t"])), "views": r["n"], "sessions": r["s"]}
        for r in qs.annotate(t=trunc).values("t").annotate(n=Count("id"), s=Count("session_hash", distinct=True)).order_by("t")
    ]
    top_products = [
        {"slug": r["product__slug"], "title": r["product__title"], "views": r["n"]}
        for r in qs.filter(product__isnull=False).values("product__slug", "product__title").annotate(n=Count("id")).order_by("-n")[:10]
    ]
    return {
        "period": period,
        "total_views": total,
        "unique_sessions": sessions,
        "product_views": qs.filter(kind=TrafficEvent.Kind.PRODUCT).count(),
        "devices": split("device"),
        "tiers": split("tier"),
        "trend": trend,
        "top_products": top_products,
        "top_referrers": [{"host": r["referrer_host"], "views": r["n"]} for r in
                          qs.exclude(referrer_host="").values("referrer_host").annotate(n=Count("id")).order_by("-n")[:8]],
        "top_categories": [{"slug": r["category_slug"], "views": r["n"]} for r in
                           qs.exclude(category_slug="").values("category_slug").annotate(n=Count("id")).order_by("-n")[:8]],
    }


def prune(days=None):
    days = days or settings.TRAFFIC_RETENTION_DAYS
    deleted, _ = TrafficEvent.objects.filter(created_at__lt=timezone.now() - timedelta(days=days)).delete()
    return deleted
