"""
Factory reset: remove all content and reset settings to blank defaults. Accounts are kept.

KEPT:    user accounts, passwords, roles & permission matrix, theme presets, AI assistant settings.
REMOVED: products, categories, photos, homepage sections/hero/menus/footer, translations, orders,
         enquiries, stock + movement log, production batches, invoices, payments, expenses, traffic.
BLANK:   brand name, tagline, contact details and announcement text (colours and layout stay).

A full JSON backup is written first to backend/backups/.   Same as Studio → System → Reset site.
Usage:  python manage.py reset_site --yes [--sample]
"""

from django.core.management.base import BaseCommand, CommandError

from ops.maintenance import reset_site


class Command(BaseCommand):
    help = "Remove all content and reset settings to blank defaults. Keeps user accounts."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Confirm the reset (required).")
        parser.add_argument("--sample", action="store_true", help="Load the sample products and homepage afterwards.")

    def handle(self, *args, **opts):
        if not opts["yes"]:
            raise CommandError("This deletes site content. Re-run with --yes. Accounts are kept.")
        out = reset_site(load_sample=opts["sample"], stdout=self.stdout)
        for label, n in out["cleared"].items():
            self.stdout.write(f"  cleared {label}: {n}")
        self.stdout.write(self.style.SUCCESS(f"Site reset. Accounts kept. Backup: {out['backup']}"))
