"""
Whenever the owner saves or deletes anything that appears on the homepage,
forget the cached /api/bootstrap so the website updates immediately.
"""

from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .utils import clear_site_cache

WATCHED = {
    "storefront": {"brandsettings", "themepreset", "activetheme", "festivalschedule", "heroslide", "pagesection", "aiassistantconfig",
                   "heromedia", "sectionmedia", "sitedesign", "navlink", "footercolumn", "footerlink"},
    "catalog": {"category", "badge", "ingredient", "product", "productimage", "productvariant", "packageoption"},
}


def _is_watched(sender):
    meta = getattr(sender, "_meta", None)
    return bool(meta) and meta.model_name in WATCHED.get(meta.app_label, set())


@receiver(post_save)
@receiver(post_delete)
def clear_on_change(sender, **kwargs):
    if _is_watched(sender):
        clear_site_cache()


@receiver(m2m_changed)
def clear_on_m2m(sender, instance, **kwargs):
    if _is_watched(type(instance)):
        clear_site_cache()
