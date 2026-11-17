"""
SEO helpers:
  • /sitemap.xml  — every live product + category, streamed so it stays fast at 50,000+ products
  • /robots.txt   — points search engines at the sitemap
  • spa_view      — serves the built React app with real Open Graph tags for /p/<slug>,
                    so WhatsApp / Facebook link previews show the product photo, name and price.
"""

from html import escape

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from catalog.models import Category, Product
from storefront.models import BrandSettings


def robots_txt(request):
    lines = ["User-agent: *", "Disallow: /admin/", "Disallow: /api/", "Disallow: /__preview", "Allow: /", f"Sitemap: {settings.SITE_URL}/sitemap.xml"]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def sitemap_xml(request):
    base = settings.SITE_URL

    def rows():
        yield '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        yield f"<url><loc>{base}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>\n"
        for slug in Category.objects.filter(is_active=True).values_list("slug", flat=True):
            yield f"<url><loc>{base}/?category={escape(slug)}</loc><changefreq>weekly</changefreq></url>\n"
        for slug, updated in Product.objects.live().values_list("slug", "updated_at").iterator(chunk_size=2000):
            yield f"<url><loc>{base}/p/{escape(slug)}</loc><lastmod>{updated:%Y-%m-%d}</lastmod><priority>0.8</priority></url>\n"
        yield "</urlset>\n"

    return StreamingHttpResponse(rows(), content_type="application/xml")


def _meta_tags(title, description, image, url, extra=""):
    t, d = escape(title), escape(description or "")
    img = f'<meta property="og:image" content="{escape(image)}"><meta name="twitter:image" content="{escape(image)}">' if image else ""
    return (
        f"<title>{t}</title><meta name=\"description\" content=\"{d}\">"
        f'<meta property="og:title" content="{t}"><meta property="og:description" content="{d}">'
        f'<meta property="og:url" content="{escape(url)}"><meta property="og:site_name" content="Paalvi">'
        f'<meta name="twitter:card" content="summary_large_image">{img}<link rel="canonical" href="{escape(url)}">{extra}'
    )


@xframe_options_sameorigin  # the admin's live preview shows the site in a frame
def spa_view(request, slug=None):
    """Serve frontend/dist/index.html with page-specific SEO tags injected (only if the build exists)."""
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        raise Http404("Frontend not built. Run `npm run build` in /frontend.")
    html = index.read_text(encoding="utf-8")
    brand = BrandSettings.load()
    title, desc, url = brand.default_seo_title, brand.default_seo_description, settings.SITE_URL + "/"
    image = request.build_absolute_uri(brand.og_share_image.url) if brand.og_share_image else ""
    extra = '<meta property="og:type" content="website">'
    if slug:
        p = Product.objects.live().select_related("category").prefetch_related("images").filter(slug=slug).first()
        if p:
            title = f"{p.seo_title or p.title} — ₹{p.retail_price:.0f} | {brand.brand_name}"
            desc = p.seo_description or p.subtitle or p.description[:155]
            url = p.get_absolute_url()
            first = next(iter(p.images.all()), None)
            if first:
                image = request.build_absolute_uri(first.medium.url)
            extra = (
                '<meta property="og:type" content="product">'
                f'<meta property="product:price:amount" content="{p.retail_price:.0f}">'
                '<meta property="product:price:currency" content="INR">'
            )
    tags = _meta_tags(title, desc, image, url, extra)
    # Swap the default <title>/description block for page-specific tags.
    start, end = "<!--paalvi:seo-->", "<!--/paalvi:seo-->"
    if start in html and end in html:
        html = html[: html.index(start)] + tags + html[html.index(end) + len(end):]
    else:
        html = html.replace("</head>", tags + "</head>", 1)
    return HttpResponse(html)


def spa_asset(request, path):
    """Serve built JS/CSS/images from frontend/dist when Django is hosting the frontend."""
    target = (settings.FRONTEND_DIST / path).resolve()
    if not str(target).startswith(str(settings.FRONTEND_DIST.resolve())) or not target.is_file():
        raise Http404()
    resp = FileResponse(open(target, "rb"))
    if path.startswith("assets/"):
        resp["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp
