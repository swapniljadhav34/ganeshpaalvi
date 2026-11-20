"""
Static website export — the storefront as plain files (no prices, no server) for Hostinger shared hosting,
Netlify, GitHub Pages or any web host.

  python manage.py export_static_site [--site-url https://paalvi.in]
  …or the "Download static website" button on the admin dashboard.

Output: <repo>/static_site/ (upload its contents to public_html) and <repo>/static_site.zip.
"""

import json
import os
import re
import shutil
import subprocess
import threading
from html import escape
from pathlib import Path
from urllib.parse import unquote

from django.conf import settings
from django.core.cache import cache
from django.test import RequestFactory, override_settings

from api import serializers as s
from api.api import _product_detail, build_bootstrap, categories_tree
from api.search import filter_products
from api.seo import _json_script, _meta_tags
from catalog.models import Product, ProductVariant
from storefront.models import BrandSettings
from storefront.utils import BOOTSTRAP_CACHE_KEY

REPO = settings.BASE_DIR.parent
FRONTEND = REPO / "frontend"
OUT_DIR = REPO / "static_site"
ZIP_PATH = REPO / "static_site.zip"

PRICE_KEYS = {"mrp", "retail_price", "wholesale_price", "discount_percent", "price_override"}
MEDIA_RE = re.compile(r'(?:(?<=")|(?<=\s)|(?<=,))/media/[^\s,"]+')

_lock = threading.Lock()


class ExportError(Exception):
    pass


def strip_prices(obj):
    if isinstance(obj, dict):
        return {k: (None if k in PRICE_KEYS else strip_prices(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [strip_prices(v) for v in obj]
    return obj


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str), encoding="utf-8")


def _build_frontend(log):
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        raise ExportError("Node.js is not installed (npm not found). Install Node 20+ from nodejs.org and try again.")
    env = {**os.environ, "VITE_STATIC": "1", "VITE_API_URL": ""}
    if not (FRONTEND / "node_modules").is_dir():
        log("Installing website packages (first time only)...")
        subprocess.run([npm, "ci"], cwd=FRONTEND, env=env, check=True)
    log("Building the website...")
    res = subprocess.run([npm, "run", "build", "--", "--outDir", str(OUT_DIR), "--emptyOutDir"],
                         cwd=FRONTEND, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise ExportError("The website build failed:\n" + (res.stderr or res.stdout)[-3000:])


def _catalog(req):
    """Every live product card, in 'featured' order, plus the extra fields the in-browser search/filters need."""
    qs = filter_products(Product.objects.live(), sort="featured")
    extra = {pk: (tags, suitable, created, sku, ean) for pk, tags, suitable, created, sku, ean in
             Product.objects.live().values_list("pk", "tags", "suitable_for", "created_at", "sku", "ean")}
    variants = {}
    for pid, vtype, value in ProductVariant.objects.filter(product__is_active=True).values_list("product_id", "variant_type", "value"):
        variants.setdefault(pid, []).append(f"{vtype}:{value}".lower())

    items = []
    for p in qs.for_cards():
        card = s.product_card(req, p)
        tags, suitable, created, sku, ean = extra[p.pk]
        words = [p.title, p.subtitle, tags, p.category.name if p.category_id else "", sku, ean]
        card["_f"] = {
            "s": " ".join(w for w in words if w).lower(),
            "suit": suitable or [],
            "v": variants.get(p.pk, []),
            "c": created.isoformat(),
        }
        items.append(card)

    _, nodes = categories_tree()

    def descendants(node):
        out = [node["slug"]]
        for child in node["children"]:
            out += descendants(child)
        return out

    categories = {n["slug"]: descendants(n) for n in nodes.values()}
    return {"items": items, "categories": categories}


def _copy_media(text, log):
    copied, missing = 0, 0
    root = Path(settings.MEDIA_ROOT)
    for url in sorted(set(MEDIA_RE.findall(text))):
        rel = unquote(url[len("/media/"):].split("?")[0])
        src = (root / rel).resolve()
        if root.resolve() not in src.parents or not src.is_file():
            missing += 1
            continue
        dst = OUT_DIR / "media" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    log(f"Copied {copied} images/videos" + (f" ({missing} missing files skipped)" if missing else ""))


HTACCESS = """# Paalvi static website (Apache / LiteSpeed — Hostinger shared hosting)
Options -Indexes
DirectoryIndex index.html
AddType model/gltf-binary .glb
AddType application/json .json

<IfModule mod_rewrite.c>
  RewriteEngine On
  RewriteBase /
  # /p/<product> → /p/<product>.html (share page with link-preview tags)
  RewriteCond %{REQUEST_FILENAME} !-f
  RewriteCond %{REQUEST_FILENAME}.html -f
  RewriteRule ^(.+)$ $1.html [L]
  # Everything else the app handles itself
  RewriteCond %{REQUEST_FILENAME} !-f
  RewriteCond %{REQUEST_FILENAME} !-d
  RewriteRule . /index.html [L]
</IfModule>

<IfModule mod_headers.c>
  <FilesMatch "\\.(js|css|woff2?)$">
    Header set Cache-Control "public, max-age=31536000, immutable"
  </FilesMatch>
  <FilesMatch "\\.(html|json)$">
    Header set Cache-Control "no-cache"
  </FilesMatch>
</IfModule>
"""


def _page(html, tags, boot):
    tags += _json_script(boot, "__BOOT__")
    start, end = "<!--paalvi:seo-->", "<!--/paalvi:seo-->"
    if start in html and end in html:
        return html[: html.index(start)] + tags + html[html.index(end) + len(end):]
    return html.replace("</head>", tags + "</head>", 1)


def _write_pages(boot, products, site_url):
    """index.html with the homepage data inlined, and one share page per product (WhatsApp/Facebook previews)."""
    index = OUT_DIR / "index.html"
    html = index.read_text(encoding="utf-8")
    brand = BrandSettings.load()
    name = brand.brand_name or "Shop"
    abs_url = lambda u: u if not u or u.startswith("http") else f"{site_url}{u}"  # noqa: E731

    home_tags = _meta_tags(brand.default_seo_title or name, brand.default_seo_description,
                           abs_url(boot["brand"].get("seo", {}).get("image") or ""), f"{site_url}/",
                           '<meta property="og:type" content="website">', site_name=name)
    index.write_text(_page(html, home_tags, boot), encoding="utf-8")
    (OUT_DIR / "404.html").write_text(_page(html, home_tags, boot), encoding="utf-8")

    for p in products:
        image = abs_url((p.get("images") or [{}])[0].get("medium") or "")
        title = f"{p.get('seo_title') or p['title']} | {name}"
        tags = _meta_tags(title, p.get("seo_description") or "", image, f"{site_url}/p/{p['slug']}",
                          '<meta property="og:type" content="product">', site_name=name)
        (OUT_DIR / "p").mkdir(exist_ok=True)
        (OUT_DIR / "p" / f"{p['slug']}.html").write_text(_page(html, tags, boot), encoding="utf-8")

    if site_url:
        urls = [f"{site_url}/"] + [f"{site_url}/p/{p['slug']}" for p in products]
        (OUT_DIR / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + "".join(f"<url><loc>{escape(u)}</loc></url>" for u in urls) + "</urlset>\n", encoding="utf-8")
        (OUT_DIR / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {site_url}/sitemap.xml\n", encoding="utf-8")


def download_view(request):
    """Admin button: build the static website and download it as a ZIP (super admins only)."""
    from django.core.exceptions import PermissionDenied
    from django.http import FileResponse, HttpResponseNotAllowed, JsonResponse

    if not request.user.is_superuser:
        raise PermissionDenied
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        path = export_static_site(request.POST.get("site_url") or os.getenv("STATIC_SITE_URL", ""), log=lambda m: None)
    except (ExportError, subprocess.CalledProcessError) as e:
        return JsonResponse({"error": str(e)}, status=500)
    return FileResponse(path.open("rb"), as_attachment=True, filename="paalvi-static-website.zip")


def export_static_site(site_url="", log=print):
    """Build the static website. Returns the path of the ZIP file."""
    if not _lock.acquire(blocking=False):
        raise ExportError("A static website build is already running. Please wait for it to finish.")
    try:
        site_url = (site_url or "").strip().rstrip("/")
        _build_frontend(log)

        log("Exporting products and pages...")
        req = RequestFactory().get("/")
        # Media links become /media/… (copied next to the site); product links point at the static site.
        with override_settings(MEDIA_BASE_URL="", SITE_URL=site_url):
            cache.delete(BOOTSTRAP_CACHE_KEY)
            try:
                boot = build_bootstrap(req)
            finally:
                cache.delete(BOOTSTRAP_CACHE_KEY)
            catalog = _catalog(req)
            details = [_product_detail(req, c["slug"]) for c in catalog["items"]]

        boot = strip_prices(boot)
        boot["ai"] = {**(boot.get("ai") or {}), "active": False}
        design = boot.get("design") or {}
        if "price" in (design.get("footer_legal_text") or "").lower():
            design["footer_legal_text"] = ""
        design["show_tier_toggle"] = False
        catalog = strip_prices(catalog)
        details = strip_prices(details)

        data = OUT_DIR / "data"
        _write_json(data / "bootstrap.json", boot)
        _write_json(data / "products.json", catalog)
        for d in details:
            _write_json(data / "products" / f"{d['slug']}.json", d)
        log(f"Exported {len(details)} products")

        _copy_media(json.dumps([boot, catalog, details], ensure_ascii=False), log)
        _write_pages(boot, details, site_url)
        (OUT_DIR / ".htaccess").write_text(HTACCESS, encoding="utf-8")
        (OUT_DIR / "_redirects").write_text("/p/:slug  /p/:slug.html  200\n/*  /index.html  200\n", encoding="utf-8")

        ZIP_PATH.unlink(missing_ok=True)
        shutil.make_archive(str(ZIP_PATH.with_suffix("")), "zip", OUT_DIR)
        log(f"Done. Upload the contents of {OUT_DIR} (or {ZIP_PATH.name}) to your host.")
        return ZIP_PATH
    finally:
        _lock.release()
