"""
python manage.py run_daily

The nightly housekeeping job (scheduled by deploy/setup.sh and the docker 'scheduler' service):
  • re-checks every stock item's alerts (expiry dates move closer every day),
  • marks unpaid invoices past their due date as OVERDUE,
  • deletes traffic analytics older than TRAFFIC_RETENTION_DAYS.
"""

from django.core.management.base import BaseCommand

from ops import accounting, analytics
from ops.inventory import check_all


class Command(BaseCommand):
    help = "Nightly: refresh inventory alerts, overdue invoices and prune old analytics."

    def handle(self, *args, **opts):
        items = check_all()
        overdue = accounting.refresh_overdue()
        pruned = analytics.prune()
        self.stdout.write(self.style.SUCCESS(
            f"Checked {items} stock item(s); {overdue} invoice(s) now overdue; removed {pruned} old traffic row(s)."))
