"""
python manage.py seed_ops [--staff]

Demo data for Paalvi Studio: realistic stock levels (some low, one expiring), production
batches, GST invoices with payments, expenses, a month of traffic and three demo 3D models.

--staff also creates one demo employee per role with a RANDOM password printed once.
Never use --staff on a live site you don't control.
"""

import random
import secrets
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog import glb
from catalog.models import Product
from ops import accounting as acc
from ops.inventory import adjust_stock, check_all, ensure_item
from ops.models import Expense, Invoice, InventoryItem, ProductionBatch, StaffProfile, StockMovement, TrafficEvent
from ops.production import create_batch, move_batch
from ops.roles import Role


class Command(BaseCommand):
    help = "Load demo inventory, production, accounting, traffic and 3D data."

    def add_arguments(self, parser):
        parser.add_argument("--staff", action="store_true", help="Also create demo employees (random passwords).")

    def handle(self, *args, staff=False, **opts):
        rnd = random.Random(7)
        owner = get_user_model().objects.filter(is_superuser=True).order_by("pk").first()
        products = list(Product.objects.order_by("order", "pk"))
        if not products:
            self.stderr.write("No products yet — run seed_demo first.")
            return

        # --- Stock: only for items that have never moved, so re-running is safe ---
        today = timezone.localdate()
        for i, p in enumerate(products):
            item = ensure_item(p)
            if item.movements.exists():
                continue
            qty = [480, 220, 9, 0, 6, 350, 140, 75, 260, 30, 120, 95, 18, 600, 1200, 40][i % 16]
            item.low_stock_threshold, item.reorder_point = (100, 200) if qty >= 400 else (20, 40)
            item.batch_number = f"LOT-{today:%y%m}-{i + 1:02d}"
            item.expiry_date = today + timedelta(days=[540, 420, 25, 0, 300, 45, 700, 365, 500, 210, 400, 380, 90, 720, 365, 300][i % 16]) \
                if p.unit in ("g", "ml") else None
            item.save()
            if qty:
                adjust_stock(item, StockMovement.Kind.IN, qty, "Opening stock count", owner)
            if qty > 100 and i % 3 == 0:
                adjust_stock(item, StockMovement.Kind.RESERVE, qty // 10, "Reserved for pending wholesale order", owner)

        # --- Production ---
        if not ProductionBatch.objects.exists():
            items = list(InventoryItem.objects.select_related("product").order_by("pk"))
            plans = [(2, 500, "IN_PRODUCTION"), (4, 300, "QC_TESTING"), (12, 200, "PLANNED"), (9, 400, "COMPLETED")]
            for idx, planned, status in plans:
                if idx >= len(items):
                    continue
                b = create_batch(items[idx], planned, owner, assigned_to=owner, expected_completion_date=today + timedelta(days=5 + idx),
                                 expiry_date=today + timedelta(days=720) if items[idx].product.unit in ("g", "ml") else None)
                flow = ProductionBatch.FLOW
                for s in flow[1:flow.index(ProductionBatch.Status(status)) + 1]:
                    move_batch(b.pk, s, owner, completed_quantity=planned - 12 if s == "COMPLETED" else None,
                               wastage_quantity=12 if s == "COMPLETED" else None)

        # --- Accounting ---
        if not Invoice.objects.exists():
            buyers = [("Sunrise Chemists", "27ABCDE1234F1Z5", "wholesale", "intra"), ("Goa Bay Boutique Hotel", "30PQRSX6789K1Z2", "wholesale", "inter"),
                      ("Ananya R.", "", "retail", "intra"), ("Lotus Salon & Spa", "27LMNOP4321Q1Z8", "wholesale", "intra"),
                      ("Corporate Gifts Co.", "29WXYZA1111B1Z3", "wholesale", "inter")]
            for n, (name, gstin, channel, mode) in enumerate(buyers):
                issue = today - timedelta(days=40 - n * 8)
                lines = []
                for p in rnd.sample(products, 2):
                    price = p.wholesale_price if channel == "wholesale" and p.wholesale_price else p.retail_price
                    lines.append({"description": p.title, "hsn": "9603" if "brush" in p.title.lower() else "3306",
                                  "quantity": Decimal(rnd.choice([1, 2]) if channel == "retail" else rnd.choice([144, 288, 72])),
                                  "unit_price": Decimal(price), "gst_rate": Decimal("18"), "product": p})
                inv = acc.create_invoice({"channel": channel, "customer_name": name, "customer_gstin": gstin, "tax_mode": mode,
                                          "prices_include_tax": channel == "retail", "issue_date": issue,
                                          "due_date": issue + timedelta(days=0 if channel == "retail" else 30),
                                          "place_of_supply": "Maharashtra" if mode == "intra" else "Goa"}, lines, owner)
                if n in (0, 2):
                    acc.record_payment(inv.pk, inv.total, "UPI" if n == 2 else "BANK", owner, reference_id=f"REF{1000 + n}", paid_on=issue + timedelta(days=3))
                elif n == 3:
                    acc.record_payment(inv.pk, (inv.total / 2).quantize(Decimal("1")), "BANK", owner, reference_id="NEFT88231", paid_on=issue + timedelta(days=10))
            acc.refresh_overdue()
        if not Expense.objects.exists():
            for cat, amt, vendor, days in [("RAW_MATERIALS", "48000", "Moso Bamboo Traders", 35), ("PACKAGING", "12600", "EcoPack Pune", 28),
                                           ("SHIPPING", "4300", "Delhivery", 20), ("UTILITIES", "3800", "MSEDCL", 15),
                                           ("PAYROLL", "65000", "Staff salaries", 5), ("MARKETING", "9000", "Instagram ads", 9)]:
                amount = Decimal(amt)
                gst = Decimal("0") if cat in ("PAYROLL", "UTILITIES") else (amount * Decimal("18") / Decimal("118")).quantize(Decimal("0.01"))
                Expense.objects.create(category=cat, amount=amount, gst_amount=gst, vendor=vendor, spent_on=today - timedelta(days=days),
                                       recorded_by=owner)

        # --- Traffic (30 days) ---
        if not TrafficEvent.objects.exists():
            now = timezone.now()
            rows = []
            for d in range(30):
                for _ in range(rnd.randint(40, 120)):
                    p = rnd.choice(products) if rnd.random() < 0.45 else None
                    rows.append(TrafficEvent(
                        kind="product" if p else "pageview", path=f"/p/{p.slug}" if p else "/", product=p,
                        device=rnd.choices(["mobile", "desktop", "tablet"], [70, 25, 5])[0],
                        tier=rnd.choices(["retail", "wholesale"], [78, 22])[0], session_hash=f"{rnd.getrandbits(48):012x}",
                        referrer_host=rnd.choice(["", "", "instagram.com", "google.com", "wa.me", "facebook.com"]),
                        created_at=now - timedelta(days=d, minutes=rnd.randint(0, 1439))))
            TrafficEvent.objects.bulk_create(rows, batch_size=1000)

        # --- 3D models ---
        models3d = [("brush", glb.toothbrush), ("tube", glb.tube), ("kit", glb.gift_box)]
        picks = {"brush": next((p for p in products if "brush" in p.title.lower()), None),
                 "tube": next((p for p in products if "paste" in p.title.lower() or "gel" in p.title.lower()), None),
                 "kit": next((p for p in products if "box" in p.title.lower() or "kit" in p.title.lower()), None)}
        for order, (key, build) in enumerate(models3d):
            p = picks[key]
            if p and not p.model_3d:
                p.model_3d.save(f"{p.slug}.glb", ContentFile(build()), save=False)
                p.is_hero_3d_featured, p.hero_3d_order = True, order
                p.save()

        check_all()

        if staff:
            self.stdout.write(self.style.WARNING("Demo staff (passwords are shown once — store them safely):"))
            User = get_user_model()
            for role in [r for r in Role if r != Role.SUPER_ADMIN]:
                username = f"demo_{role.value.lower()}"
                user, created = User.objects.get_or_create(username=username, defaults={"first_name": role.label})
                password = secrets.token_urlsafe(9)
                user.set_password(password)
                user.save()
                StaffProfile.objects.update_or_create(user=user, defaults={"role": role})
                self.stdout.write(f"  {username:28} {password}   ({role.label})")

        self.stdout.write(self.style.SUCCESS("Operations demo data ready. Open /studio to explore."))
