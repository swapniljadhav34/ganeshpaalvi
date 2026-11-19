"""
Tests for the money- and security-critical behaviour:
  • role permissions are enforced on the server (accounting is super admin + accountant only),
  • stock changes are atomic, validated and always logged; alerts raise and resolve themselves,
  • completing a production batch adds stock exactly once,
  • invoice numbers / GST maths / payments,
  • plus the production-readiness fixes (rate-limit IP, query caps, 404s, uploads, CSV formulas).

Run:  python manage.py test
"""

import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from catalog import glb
from catalog.models import Category, Product
from storefront import validators as V

from . import accounting as acc
from .inventory import StockError, adjust_stock, ensure_item
from .models import InventoryAlert, InventoryItem, Invoice, ProductionBatch, StaffProfile, StockMovement, TrafficEvent
from .production import create_batch, move_batch
from .roles import Role

User = get_user_model()
JSON = "application/json"


def make_product(sku="T-1", title="Test Brush", **kw):
    cat, _ = Category.objects.get_or_create(name="Brushes")
    return Product.objects.create(sku=sku, title=title, category=cat, mrp=Decimal("100"), retail_price=Decimal("90"), **kw)


def make_user(username, role=None, superuser=False):
    u = User.objects.create_user(username=username, password="pw-123456!", is_superuser=superuser, is_staff=superuser)
    if role:
        StaffProfile.objects.create(user=u, role=role)
    return u


class StudioClient(Client):
    """A browser-like client that does the CSRF dance like the real Studio."""

    def __init__(self):
        super().__init__(enforce_csrf_checks=True)

    def login_as(self, user):
        self.force_login(user)
        self.get("/api/staff/auth/csrf")

    def _h(self):
        return {"HTTP_X_CSRFTOKEN": self.cookies["csrftoken"].value} if "csrftoken" in self.cookies else {}

    def jpost(self, url, data=None):
        return self.post(url, json.dumps(data or {}), content_type=JSON, **self._h())

    def jpatch(self, url, data=None):
        return self.patch(url, json.dumps(data or {}), content_type=JSON, **self._h())


class BaseCase(TestCase):
    def setUp(self):
        cache.clear()
        self.product = make_product()
        self.item = InventoryItem.objects.get(product=self.product)
        self.owner = make_user("owner", superuser=True)


class PermissionTests(BaseCase):
    def test_accounting_is_only_for_super_admin_and_accountant(self):
        for role, allowed in [(Role.ACCOUNTANT, True), (Role.INVENTORY_MANAGER, False), (Role.EMPLOYEE_OPS, False),
                              (Role.PRODUCTION_MANAGER, False), (Role.EMPLOYEE_CATALOG, False), (Role.WHOLESALE_MANAGER, False)]:
            c = StudioClient()
            c.login_as(make_user(f"u_{role}", role))
            r = c.get("/api/staff/accounting/summary")
            self.assertEqual(r.status_code, 200 if allowed else 403, role)
        c = StudioClient()
        c.login_as(self.owner)
        self.assertEqual(c.get("/api/staff/accounting/summary").status_code, 200)

    def test_anonymous_and_roleless_users_are_refused(self):
        self.assertEqual(Client().get("/api/staff/inventory/items").status_code, 401)
        c = StudioClient()
        c.login_as(make_user("customer"))  # logged in, but no staff role
        self.assertEqual(c.get("/api/staff/inventory/items").status_code, 403)
        self.assertEqual(c.get("/api/staff/auth/me").status_code, 403)

    def test_writes_need_csrf_token(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(make_user("ops", Role.EMPLOYEE_OPS))
        r = c.post(f"/api/staff/inventory/items/{self.item.pk}/adjust",
                   json.dumps({"kind": "IN", "quantity": 5, "reason": "count"}), content_type=JSON)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_audit_log_export_and_thresholds_are_admin_only(self):
        c = StudioClient()
        c.login_as(make_user("invmgr", Role.INVENTORY_MANAGER))
        self.assertEqual(c.get("/api/staff/inventory/movements").status_code, 403)
        self.assertEqual(c.get("/api/staff/inventory/export.csv").status_code, 403)
        self.assertEqual(c.jpatch(f"/api/staff/inventory/items/{self.item.pk}/thresholds",
                                  {"low_stock_threshold": 1, "reorder_point": 2}).status_code, 403)
        c.login_as(self.owner)
        self.assertEqual(c.get("/api/staff/inventory/movements").status_code, 200)
        self.assertEqual(c.get("/api/staff/inventory/export.csv").status_code, 200)

    def test_employees_cannot_manage_staff(self):
        c = StudioClient()
        c.login_as(make_user("ops2", Role.EMPLOYEE_OPS))
        self.assertEqual(c.get("/api/staff/team").status_code, 403)
        self.assertEqual(c.jpost("/api/staff/team", {"username": "evil", "role": "SUPER_ADMIN"}).status_code, 403)
        self.assertFalse(User.objects.filter(username="evil").exists())

    def test_login_returns_role_permissions_and_tabs(self):
        make_user("acct", Role.ACCOUNTANT)
        c = StudioClient()
        c.get("/api/staff/auth/csrf")
        r = c.jpost("/api/staff/auth/login", {"username": "acct", "password": "pw-123456!"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["role"], "ACCOUNTANT")
        self.assertEqual([t["key"] for t in body["tabs"]], ["accounting"])
        self.assertNotIn("inventory.view", body["permissions"])

    def test_role_profile_controls_django_admin_access(self):
        u = make_user("boss")
        StaffProfile.objects.create(user=u, role=Role.SUPER_ADMIN)
        u.refresh_from_db()
        self.assertTrue(u.is_superuser and u.is_staff)
        emp = make_user("emp", Role.EMPLOYEE_CATALOG)
        self.assertFalse(emp.is_staff)  # employees never get /admin/


class InventoryTests(BaseCase):
    def test_every_change_is_logged_and_atomic(self):
        adjust_stock(self.item, "IN", 50, "Opening count", self.owner)
        adjust_stock(self.item, "OUT", 20, "Sale", self.owner)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock_quantity, 30)
        self.assertEqual(list(StockMovement.objects.order_by("pk").values_list("quantity", "stock_after")), [(50, 50), (-20, 30)])
        with self.assertRaises(StockError):
            adjust_stock(self.item, "OUT", 31, "Too many", self.owner)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock_quantity, 30)  # nothing changed
        self.assertEqual(StockMovement.objects.count(), 2)  # and nothing was logged

    def test_reason_is_required_and_log_is_immutable(self):
        with self.assertRaises(StockError):
            adjust_stock(self.item, "IN", 5, "   ", self.owner)
        mv = adjust_stock(self.item, "IN", 5, "ok", self.owner)
        mv.reason = "edited"
        with self.assertRaises(ValidationError):
            mv.save()
        with self.assertRaises(ValidationError):
            mv.delete()

    def test_alerts_raise_and_resolve_automatically(self):
        self.item.low_stock_threshold, self.item.reorder_point = 10, 20
        self.item.save()
        active = lambda: set(InventoryAlert.objects.filter(item=self.item, is_active=True).values_list("kind", flat=True))  # noqa: E731
        adjust_stock(self.item, "IN", 5, "count")
        self.assertEqual(active(), {"LOW_STOCK", "PRODUCTION_NEEDED"})
        adjust_stock(self.item, "OUT", 5, "sale")
        self.assertEqual(active(), {"OUT_OF_STOCK", "PRODUCTION_NEEDED"})
        adjust_stock(self.item, "IN", 100, "delivery")
        self.assertEqual(active(), set())
        self.item.expiry_date = timezone.localdate() + timedelta(days=10)
        self.item.save()
        adjust_stock(self.item, "OUT", 1, "sale")
        self.assertEqual(active(), {"EXPIRING_SOON"})

    def test_reservations_reduce_available_stock(self):
        adjust_stock(self.item, "IN", 30, "count")
        adjust_stock(self.item, "RESERVE", 25, "Order #12")
        self.item.refresh_from_db()
        self.assertEqual((self.item.stock_quantity, self.item.reserved_quantity, self.item.available), (30, 25, 5))
        adjust_stock(self.item, "WHOLESALE_DISPATCH", 25, "Order #12 shipped", release_reserved=25)
        self.item.refresh_from_db()
        self.assertEqual((self.item.stock_quantity, self.item.reserved_quantity), (5, 0))

    def test_storefront_label_follows_stock(self):
        adjust_stock(self.item, "IN", 100, "count")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_status, "in_stock")
        adjust_stock(self.item, "OUT", 100, "sold out")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_status, "out_of_stock")

    def test_api_adjust_requires_permission_and_validates(self):
        c = StudioClient()
        c.login_as(make_user("ops", Role.EMPLOYEE_OPS))
        url = f"/api/staff/inventory/items/{self.item.pk}/adjust"
        self.assertEqual(c.jpost(url, {"kind": "IN", "quantity": 10, "reason": "count"}).status_code, 200)
        self.assertEqual(c.jpost(url, {"kind": "OUT", "quantity": 99, "reason": "sale"}).status_code, 400)
        self.assertEqual(c.jpost(url, {"kind": "PRODUCTION_IN", "quantity": 5, "reason": "x"}).status_code, 422)  # only via batches
        c2 = StudioClient()
        c2.login_as(make_user("cat", Role.EMPLOYEE_CATALOG))
        self.assertEqual(c2.jpost(url, {"kind": "IN", "quantity": 1, "reason": "count"}).status_code, 403)


class ProductionTests(BaseCase):
    def test_completion_adds_stock_once_and_clears_flags(self):
        self.item.reorder_point, self.item.low_stock_threshold = 50, 20
        self.item.save()
        adjust_stock(self.item, "IN", 5, "count")
        self.assertTrue(InventoryAlert.objects.filter(item=self.item, kind="PRODUCTION_NEEDED", is_active=True).exists())
        batch = create_batch(self.item, 200, self.owner, expiry_date=timezone.localdate() + timedelta(days=700))
        self.assertFalse(InventoryAlert.objects.filter(item=self.item, kind="PRODUCTION_NEEDED", is_active=True).exists())
        for s in ProductionBatch.FLOW[1:-1]:
            move_batch(batch.pk, s, self.owner)
        move_batch(batch.pk, "COMPLETED", self.owner, completed_quantity=190, wastage_quantity=10)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock_quantity, 195)
        self.assertEqual(self.item.batch_number, batch.batch_code)
        self.assertEqual(StockMovement.objects.filter(kind="PRODUCTION_IN", production_batch=batch).count(), 1)
        self.assertFalse(InventoryAlert.objects.filter(item=self.item, is_active=True, kind__in=["LOW_STOCK", "PRODUCTION_NEEDED"]).exists())
        with self.assertRaises(StockError):
            move_batch(batch.pk, "COMPLETED", self.owner, completed_quantity=190)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock_quantity, 195)

    def test_only_assignee_or_manager_moves_a_batch(self):
        worker, other = make_user("w1", Role.EMPLOYEE_OPS), make_user("w2", Role.EMPLOYEE_OPS)
        batch = create_batch(self.item, 10, self.owner, assigned_to=worker)
        url = f"/api/staff/production/batches/{batch.pk}/move"
        c = StudioClient()
        c.login_as(other)
        self.assertEqual(c.jpost(url, {"status": "RAW_MATERIALS_READY"}).status_code, 403)
        c.login_as(worker)
        self.assertEqual(c.jpost(url, {"status": "RAW_MATERIALS_READY"}).status_code, 200)
        self.assertEqual(c.jpost(url, {"status": "CANCELLED"}).status_code, 403)  # managers only


class AccountingTests(BaseCase):
    def test_invoice_numbers_gst_and_payments(self):
        self.assertEqual(acc.financial_year(timezone.datetime(2027, 3, 31).date()), "2026-27")
        self.assertEqual(acc.financial_year(timezone.datetime(2027, 4, 1).date()), "2027-28")
        line = {"description": "Brush", "hsn": "9603", "quantity": Decimal("10"), "unit_price": Decimal("100"),
                "gst_rate": Decimal("18"), "product": None}
        today = timezone.localdate()
        intra = acc.create_invoice({"customer_name": "A", "tax_mode": "intra", "issue_date": today, "due_date": today + timedelta(days=30)},
                                   [line], self.owner)
        inter = acc.create_invoice({"customer_name": "B", "tax_mode": "inter", "issue_date": today, "due_date": today}, [line], self.owner)
        self.assertNotEqual(intra.number, inter.number)
        self.assertEqual((intra.subtotal, intra.cgst, intra.sgst, intra.igst, intra.total),
                         (Decimal("1000.00"), Decimal("90.00"), Decimal("90.00"), Decimal("0.00"), Decimal("1180.00")))
        self.assertEqual((inter.igst, inter.total), (Decimal("180.00"), Decimal("1180.00")))
        acc.record_payment(intra.pk, "500", "UPI", self.owner)
        intra.refresh_from_db()
        self.assertEqual(intra.payment_status, Invoice.PaymentStatus.PARTIAL)
        with self.assertRaises(acc.AccountingError):
            acc.record_payment(intra.pk, "700", "UPI", self.owner)  # more than the balance
        acc.record_payment(intra.pk, "680", "BANK", self.owner)
        intra.refresh_from_db()
        self.assertEqual(intra.payment_status, Invoice.PaymentStatus.PAID)

    def test_prices_including_gst_are_split_correctly(self):
        taxable, tax = acc.line_amounts(Decimal("1"), Decimal("118"), Decimal("18"), True)
        self.assertEqual((taxable, tax), (Decimal("100.00"), Decimal("18.00")))

    def test_csv_export_neutralises_formulas(self):
        self.assertEqual(acc.safe_cell("=HYPERLINK(\"x\")"), "'=HYPERLINK(\"x\")")
        self.assertEqual(acc.safe_cell("Ravi"), "Ravi")


class AnalyticsTests(BaseCase):
    def test_track_ignores_bots_and_summary_is_admin_only(self):
        c = Client()
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile"
        c.post("/api/analytics/track", json.dumps({"path": f"/p/{self.product.slug}", "sid": "abc"}), content_type=JSON, HTTP_USER_AGENT=ua)
        c.post("/api/analytics/track", json.dumps({"path": "/"}), content_type=JSON, HTTP_USER_AGENT="Googlebot/2.1")
        ev = TrafficEvent.objects.get()
        self.assertEqual((ev.kind, ev.device, ev.product_id), ("product", "mobile", self.product.pk))
        s = StudioClient()
        s.login_as(make_user("w", Role.WHOLESALE_MANAGER))
        self.assertEqual(s.get("/api/staff/analytics/summary").status_code, 403)
        s.login_as(self.owner)
        self.assertEqual(s.get("/api/staff/analytics/summary?period=7d").json()["total_views"], 1)


class UploadTests(TestCase):
    def test_glb_validation(self):
        V.run(V.MODEL_3D, SimpleUploadedFile("brush.glb", glb.toothbrush()))
        with self.assertRaises(ValidationError):
            V.run(V.MODEL_3D, SimpleUploadedFile("evil.glb", b"<html><script>alert(1)</script></html>"))
        with self.assertRaises(ValidationError):
            V.run(V.MODEL_3D, SimpleUploadedFile("brush.html", glb.toothbrush()))

    def test_videos_and_logos_reject_html(self):
        for validators in (V.VIDEO, V.LOGO):
            with self.assertRaises(ValidationError):
                V.run(validators, SimpleUploadedFile("x.html", b"<script></script>"))


class ReviewFixTests(BaseCase):
    @override_settings(CLIENT_IP_HEADER="HTTP_X_REAL_IP", RATE_LIMIT_INQUIRY_PER_MIN=3)
    def test_rate_limit_ignores_forged_forwarded_for(self):
        codes = [Client().post("/api/inquiry", json.dumps({"website": "bot"}), content_type=JSON,
                               HTTP_X_FORWARDED_FOR=f"9.9.9.{i}", HTTP_X_REAL_IP="1.2.3.4").status_code for i in range(5)]
        self.assertEqual(codes, [200, 200, 200, 429, 429])

    def test_filter_lists_are_capped(self):
        r = Client().get("/api/products?badge=" + ",".join(f"b{i}" for i in range(70)))
        self.assertEqual(r.status_code, 200)

    def test_unknown_product_page_is_a_real_404(self):
        from django.conf import settings

        if not (settings.FRONTEND_DIST / "index.html").exists():
            self.skipTest("frontend not built")
        self.assertEqual(Client().get("/p/does-not-exist").status_code, 404)
        r = Client().get(f"/p/{self.product.slug}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'"@type": "Product"', r.content)
        self.assertIn(b'id="__BOOT__"', r.content)

    def test_media_urls_do_not_depend_on_host_header(self):
        from api.serializers import media_url

        self.product.model_3d.save("m.glb", SimpleUploadedFile("m.glb", glb.tube()), save=True)
        from django.conf import settings

        self.assertTrue(media_url(None, self.product.model_3d).startswith(settings.MEDIA_BASE_URL))

    def test_enquiry_needs_consent(self):
        base = {"name": "Ravi", "phone": "9876543210", "source": "contact"}
        r = Client().post("/api/inquiry", json.dumps(base), content_type=JSON)
        self.assertEqual(r.status_code, 422)
        r = Client().post("/api/inquiry", json.dumps({**base, "consent": True}), content_type=JSON)
        self.assertEqual(r.status_code, 200)

    def test_new_products_get_a_stock_item(self):
        p = make_product(sku="NEW-9", title="New Paste")
        self.assertTrue(InventoryItem.objects.filter(product=p, sku="NEW-9").exists())
        self.assertEqual(ensure_item(p).pk, InventoryItem.objects.get(product=p).pk)
