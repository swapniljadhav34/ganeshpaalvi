import os

from django.core.management.base import BaseCommand, CommandError

from storefront.static_export import ExportError, export_static_site


class Command(BaseCommand):
    help = "Build the storefront as a static website without prices (for Hostinger shared hosting or any web host)."

    def add_arguments(self, parser):
        parser.add_argument("--site-url", default="", help="Address the static site will live at, e.g. https://paalvi.in "
                                                           "(used for share previews and the sitemap).")

    def handle(self, *args, site_url="", **opts):
        try:
            export_static_site(site_url or os.getenv("STATIC_SITE_URL", ""), log=lambda m: self.stdout.write(m))
        except ExportError as e:
            raise CommandError(str(e))
