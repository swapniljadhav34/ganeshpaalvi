"""
Paalvi URL map.

  /admin/          Paalvi Studio (owner admin)
  /api/...         public JSON API used by the React site
  /sitemap.xml     auto-generated sitemap
  /robots.txt      search-engine rules
  /p/<slug>        product share page (React app + real link-preview tags), if the frontend is built here
  /                React app (if built into frontend/dist)
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path

from api.api import api
from api.seo import robots_txt, sitemap_xml, spa_asset, spa_view

admin.site.site_header = "Paalvi Studio"
admin.site.site_title = "Paalvi Studio"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("sitemap.xml", sitemap_xml, name="sitemap"),
    path("robots.txt", robots_txt, name="robots"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Optional: let Django host the built React app (single-server deploys).
urlpatterns += [
    path("p/<slug:slug>", spa_view, name="product-share"),
    path("__preview", spa_view, name="admin-preview"),
    re_path(r"^(?P<path>(assets/.+|favicon\.svg|.+\.(?:png|ico|webmanifest|svg|txt|jpg|webp)))$", spa_asset),
    path("", spa_view, name="spa-home"),
]
