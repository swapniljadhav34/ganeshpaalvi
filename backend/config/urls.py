"""
Paalvi URL map.

  /<ADMIN_URL>     Paalvi Studio admin settings (super admins). Default /admin/ — move it with ADMIN_URL.
  /api/...         public JSON API used by the React site, plus /api/staff/ for Paalvi Studio
  /studio/...      Paalvi Studio for employees (React, role-based tabs)
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
from api.seo import robots_txt, sitemap_xml, spa_asset, spa_view, studio_view, track_view

admin.site.site_header = "Designer"  # the sidebar title follows the brand name (settings.UNFOLD)
admin.site.site_title = "Designer"
admin.site.index_title = "Dashboard"

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/", api.urls),
    path("sitemap.xml", sitemap_xml, name="sitemap"),
    path("robots.txt", robots_txt, name="robots"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Django hosts the built React app (single-server deploys). Built JS/CSS is served by WhiteNoise.
urlpatterns += [
    path("p/<slug:slug>", spa_view, name="product-share"),
    path("privacy", spa_view, name="privacy"),
    path("track", track_view, name="track"),
    path("track/<str:token>", track_view, name="track-link"),
    path("studio", studio_view, name="studio"),
    re_path(r"^studio/(?P<rest>.*)$", studio_view),
    path("__preview", studio_view, name="admin-preview"),
    re_path(r"^(?P<path>(assets/.+|favicon\.svg|.+\.(?:png|ico|webmanifest|svg|txt|jpg|webp)))$", spa_asset),
    path("", spa_view, name="spa-home"),
]
