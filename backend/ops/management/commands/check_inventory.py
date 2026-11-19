"""python manage.py check_inventory — re-evaluate every stock item's automatic alerts now."""

from django.core.management.base import BaseCommand

from ops.inventory import check_all


class Command(BaseCommand):
    help = "Raise / resolve inventory alerts for every stock item (out of stock, low, expiring, production needed)."

    def handle(self, *args, **opts):
        self.stdout.write(self.style.SUCCESS(f"Checked {check_all()} stock item(s)."))
