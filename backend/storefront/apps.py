from django.apps import AppConfig


class StorefrontConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "storefront"
    verbose_name = "Brand, Theme & Homepage"

    def ready(self):
        from . import signals  # noqa: F401  (connects the cache-clearing signals)
