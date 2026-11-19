"""
System maintenance (Admin only): health check, cache clear, one-click recovery and site reset.

None of these need a server restart:
  • clear_caches()  — forgets cached homepage/product data, role matrix and the cached index.html.
  • recover()       — clear_caches + re-checks every stock alert and storefront stock label, marks
                      overdue invoices, removes expired login sessions and lifts login lockouts.
  • reset_site()    — writes a JSON backup, then removes all content and resets settings to blank
                      defaults. User accounts, roles and passwords are always kept.
"""

import logging
import time
from datetime import datetime
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection, transaction

log = logging.getLogger("paalvi")

# Deleted children-first so foreign keys never block. Stock movements are immutable through the ORM,
# so everything is removed with raw deletes (no per-row signals).
WIPE_ORDER = [
    "ops.OrderEvent", "ops.OrderLine", "ops.Order",
    "ops.PaymentRecord", "ops.InvoiceLine", "ops.Invoice", "ops.InvoiceSequence", "ops.Expense",
    "ops.StockMovement", "ops.InventoryAlert", "ops.ProductionBatch", "ops.InventoryItem",
    "ops.TrafficEvent",
    "leads.LeadInquiry",
    "storefront.HeroMedia", "storefront.SectionMedia", "storefront.HeroSlide", "storefront.PageSection",
    "storefront.NavLink", "storefront.FooterLink", "storefront.FooterColumn", "storefront.UiTranslation",
    "catalog.PackageOption", "catalog.ProductVariant", "catalog.ProductImage",
    "catalog.Product", "catalog.Badge", "catalog.Ingredient", "catalog.Category",
]
SINGLETONS = ["storefront.BrandSettings", "storefront.SiteDesign", "ops.InventorySettings"]
BLANK_BRAND_FIELDS = [
    "brand_name", "tagline", "contact_email", "whatsapp_number", "default_seo_title", "default_seo_description",
    "announcement_text", "announcement_link", "footer_story",
]


def clear_caches():
    from api import seo
    from storefront.utils import clear_site_cache

    from .roles import forget_role_matrix

    clear_site_cache()
    forget_role_matrix()
    seo._INDEX.update(mtime=None, html="")  # re-read the built site on the next request
    try:
        cache.clear()
    except Exception:  # some cache backends can't clear everything — the keys above are already gone
        log.warning("cache.clear() not supported by this cache backend")
    return {"cleared": True}


def recover():
    """One click: the steps an engineer would run after something got stuck. Safe to run any time."""
    from axes.models import AccessAttempt
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    from . import accounting
    from .inventory import check_all

    steps = []

    def step(label, fn):
        t = time.monotonic()
        try:
            detail = fn()
            steps.append({"label": label, "ok": True, "detail": detail, "ms": round((time.monotonic() - t) * 1000)})
        except Exception as e:  # keep going: one failed step must not stop the others
            log.exception("recovery step failed: %s", label)
            steps.append({"label": label, "ok": False, "detail": str(e)[:200], "ms": round((time.monotonic() - t) * 1000)})

    step("Cleared cached pages and settings", lambda: "done" if clear_caches() else "")
    step("Re-checked stock alerts and website stock labels", lambda: f"{check_all()} item(s)")
    step("Marked overdue invoices", lambda: f"{accounting.refresh_overdue()} invoice(s)")
    step("Removed expired login sessions",
         lambda: f"{Session.objects.filter(expire_date__lt=timezone.now()).delete()[0]} session(s)")
    step("Lifted login lockouts", lambda: f"{AccessAttempt.objects.all().delete()[0]} lockout record(s)")
    step("Database connection", lambda: (connection.ensure_connection(), "ok")[1])
    return {"steps": steps, "ok": all(s["ok"] for s in steps)}


def health():
    out = {"database": False, "cache": False}
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        out["database"] = True
    except Exception as e:
        out["database_error"] = str(e)[:200]
    try:
        cache.set("ops:health", "1", 10)
        out["cache"] = cache.get("ops:health") == "1"
    except Exception as e:
        out["cache_error"] = str(e)[:200]
    out["cache_backend"] = settings.CACHES["default"]["BACKEND"].rsplit(".", 1)[-1]
    out["database_engine"] = connection.vendor
    out["debug"] = settings.DEBUG
    out["frontend_built"] = (settings.FRONTEND_DIST / "index.html").exists()
    counts = {}
    for label in ["catalog.Product", "catalog.Category", "ops.Order", "ops.InventoryItem", "storefront.PageSection",
                  "leads.LeadInquiry", "auth.User"]:
        try:
            counts[label.split(".")[1]] = apps.get_model(label).objects.count()
        except Exception:
            counts[label.split(".")[1]] = None
    out["counts"] = counts
    backups = sorted((Path(settings.BASE_DIR) / "backups").glob("*.json"), reverse=True)[:5]
    out["backups"] = [{"name": b.name, "size_kb": round(b.stat().st_size / 1024)} for b in backups]
    return out


def write_backup(prefix="before-reset"):
    backup_dir = Path(settings.BASE_DIR) / "backups"
    backup_dir.mkdir(exist_ok=True)
    path = backup_dir / f"{prefix}-{datetime.now():%Y%m%d-%H%M%S}.json"
    with open(path, "w", encoding="utf-8") as fh:
        call_command("dumpdata", "--natural-foreign", "--indent", "2", stdout=fh,
                     exclude=["auth.permission", "contenttypes", "admin.logentry", "sessions", "axes"])
    return path


def reset_site(load_sample=False, stdout=None):
    """Factory reset of content and settings. Accounts, roles and passwords are kept. Returns a summary."""
    path = write_backup()
    cleared = {}
    with transaction.atomic():
        # Many-to-many link rows (e.g. product ↔ badge) go first.
        wiped = {apps.get_model(label) for label in WIPE_ORDER}
        for model in apps.get_models():
            for f in model._meta.local_many_to_many:
                through = f.remote_field.through
                if (model in wiped or f.related_model in wiped) and through._meta.auto_created:
                    through._base_manager.all()._raw_delete(through._base_manager.db)
        for label in WIPE_ORDER:
            model = apps.get_model(label)
            cleared[label] = model._base_manager.all()._raw_delete(model._base_manager.db)
        for label in SINGLETONS:
            model = apps.get_model(label)
            model._base_manager.all()._raw_delete(model._base_manager.db)
            row = model.load()
            if label == "storefront.BrandSettings":
                for f in BLANK_BRAND_FIELDS:
                    setattr(row, f, "")
                row.save()
    if load_sample:
        call_command("seed_demo", stdout=stdout)
    clear_caches()
    return {"backup": str(path), "cleared": cleared, "sample_loaded": load_sample}
