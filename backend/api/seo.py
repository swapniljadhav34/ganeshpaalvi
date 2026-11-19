"""
SEO + serving the built React app:
  • /sitemap.xml  — every live product, streamed so it stays fast at 50,000+ products
  • /robots.txt   — keeps crawlers out of admin, API, Studio and previews
  • spa_view      — serves frontend/dist/index.html with, per page:
        - real <title>/description/Open Graph tags (WhatsApp & Facebook previews),
        - Product JSON-LD and a plain-HTML summary for crawlers that don't run JavaScript,
        - the homepage data inlined (no extra API round trip before the hero can paint),
        - a preload hint for the hero picture (faster Largest Contentful Paint),
        - a real 404 status for unknown product links.
"""

import json
from html import escape

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from catalog.models import Product
from storefront.models import BrandSettings

_INDEX = {"mtime": None, "html": ""}


def robots_txt(request):
    # A custom ADMIN_URL is a secret — never advertise it in robots.txt.
    admin = ["Disallow: /admin/"] if settings.ADMIN_URL == "admin/" else []
    lines = ["User-agent: *", *admin, "Disallow: /api/", "Disallow: /studio", "Disallow: /__preview", "Disallow: /track", "Allow: /",
             f"Sitemap: {settings.SITE_URL}/sitemap.xml"]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def sitemap_xml(request):
    base = settings.SITE_URL

    def rows():
        yield '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        yield f"<url><loc>{base}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>\n"
        # Category filters are client-side views of "/", so they are not listed separately (no duplicate pages).
        for slug, updated in Product.objects.live().values_list("slug", "updated_at").iterator(chunk_size=2000):
            yield f"<url><loc>{base}/p/{escape(slug)}</loc><lastmod>{updated:%Y-%m-%d}</lastmod><priority>0.8</priority></url>\n"
        yield "</urlset>\n"

    return StreamingHttpResponse(rows(), content_type="application/xml")


def _json_script(data, el_id=None, kind="application/json"):
    """Embed JSON in HTML safely (a '</script>' inside any text can't break out)."""
    payload = json.dumps(data, ensure_ascii=False, default=str).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    attr = f' id="{el_id}"' if el_id else ""
    return f'<script type="{kind}"{attr}>{payload}</script>'


def _meta_tags(title, description, image, url, extra="", robots="", site_name=""):
    t, d = escape(title), escape(description or "")
    img = f'<meta property="og:image" content="{escape(image)}"><meta name="twitter:image" content="{escape(image)}">' if image else ""
    robots_tag = f'<meta name="robots" content="{robots}">' if robots else ""
    return (
        f"<title>{t}</title><meta name=\"description\" content=\"{d}\">{robots_tag}"
        f'<meta property="og:title" content="{t}"><meta property="og:description" content="{d}">'
        f'<meta property="og:url" content="{escape(url)}"><meta property="og:site_name" content="{escape(site_name)}">'
        f'<meta name="twitter:card" content="summary_large_image">{img}<link rel="canonical" href="{escape(url)}">{extra}'
    )


def _index_html():
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        raise Http404("Frontend not built. Run `npm run build` in /frontend.")
    mtime = index.stat().st_mtime
    if _INDEX["mtime"] != mtime:  # re-read only after a new build
        _INDEX.update(mtime=mtime, html=index.read_text(encoding="utf-8"))
    return _INDEX["html"]


def _fallback(title, lines):
    """Plain HTML inside #root for crawlers without JavaScript. React replaces it on load."""
    body = "".join(f"<p>{escape(str(x))}</p>" for x in lines if x)
    return (f'<main style="max-width:720px;margin:96px auto;padding:0 20px;font-family:system-ui,sans-serif;color:#14181f">'
            f"<h1>{escape(title)}</h1>{body}</main>")


@xframe_options_sameorigin  # the admin's live preview shows the site in a frame
def spa_view(request, slug=None, private=False):
    html = _index_html()
    brand = BrandSettings.load()
    title, desc, url = brand.default_seo_title or brand.brand_name or "Shop", brand.default_seo_description, settings.SITE_URL + "/"
    image = request.build_absolute_uri(brand.og_share_image.url) if brand.og_share_image else ""
    extra = '<meta property="og:type" content="website">'
    status, robots = 200, "noindex, nofollow" if private else ""
    root = _fallback(brand.brand_name, [brand.tagline, brand.default_seo_description])

    if slug:
        p = Product.objects.live().select_related("category").prefetch_related("images").filter(slug=slug).first()
        if p:
            title = f"{p.seo_title or p.title} — ₹{p.retail_price:.0f}" + (f" | {brand.brand_name}" if brand.brand_name else "")
            desc = p.seo_description or p.subtitle or p.description[:155]
            url = p.get_absolute_url()
            imgs = list(p.images.all())
            if imgs:
                image = request.build_absolute_uri(imgs[0].medium.url)
            ld = {
                "@context": "https://schema.org", "@type": "Product", "name": p.title, "description": desc, "sku": p.sku,
                "image": [request.build_absolute_uri(i.medium.url) for i in imgs[:4]],
                "brand": {"@type": "Brand", "name": brand.brand_name},
                "category": p.category.name if p.category_id else None,
                "offers": {"@type": "Offer", "priceCurrency": "INR", "price": f"{p.retail_price:.2f}", "url": url,
                           "availability": "https://schema.org/OutOfStock" if p.stock_status == Product.StockStatus.OUT
                           else "https://schema.org/InStock"},
            }
            if p.ean:
                ld["gtin13"] = p.ean
            extra = ('<meta property="og:type" content="product">'
                     f'<meta property="product:price:amount" content="{p.retail_price:.0f}">'
                     '<meta property="product:price:currency" content="INR">' + _json_script(ld, kind="application/ld+json"))
            root = _fallback(p.title, [p.subtitle, f"₹{p.retail_price:,.0f} (MRP ₹{p.mrp:,.0f}, incl. of all taxes)",
                                       p.category.name if p.category_id else "", p.description[:600]])
        else:
            status, robots = 404, "noindex"
            title, desc = "Not found" + (f" | {brand.brand_name}" if brand.brand_name else ""), "This product isn't available."
            root = _fallback("This product isn't available", ["It may have been renamed or removed."])

    tags = _meta_tags(title, desc, image, url, extra, robots, site_name=brand.brand_name)
    if not private:  # inline the homepage data + preload the hero picture
        from .api import build_bootstrap

        boot = build_bootstrap(request)
        tags += _json_script(boot, "__BOOT__")
        first = next((m for h in boot.get("hero", [])[:1] for m in h.get("media", [])[:1]), None)
        if first and not slug:
            src = first.get("poster") if first.get("type") == "video" else first.get("src")
            if src:
                srcset = f' imagesrcset="{escape(first["srcset"])}" imagesizes="100vw"' if first.get("srcset") else ""
                tags += f'<link rel="preload" as="image" href="{escape(src)}"{srcset} fetchpriority="high">'

    start, end = "<!--paalvi:seo-->", "<!--/paalvi:seo-->"
    if start in html and end in html:
        html = html[: html.index(start)] + tags + html[html.index(end) + len(end):]
    else:
        html = html.replace("</head>", tags + "</head>", 1)
    html = html.replace('<div id="root"></div>', f'<div id="root">{root}</div>', 1)
    resp = HttpResponse(html, status=status)
    resp["Cache-Control"] = "no-cache"
    if private:
        resp["X-Robots-Tag"] = "noindex, nofollow"
    return resp


def studio_view(request, rest=""):
    return spa_view(request, private=True)


def spa_asset(request, path):
    """Fallback for built files when WhiteNoise isn't serving them (normally it is)."""
    root = settings.FRONTEND_DIST.resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise Http404()
    resp = FileResponse(open(target, "rb"))
    if path.startswith("assets/"):
        resp["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


def track_view(request, token=""):
    """Order tracking pages: full site (with homepage data), but never indexed — the link is private."""
    resp = spa_view(request)
    resp["X-Robots-Tag"] = "noindex, nofollow"
    resp["Referrer-Policy"] = "no-referrer"  # don't leak the tracking link to other sites
    return resp
