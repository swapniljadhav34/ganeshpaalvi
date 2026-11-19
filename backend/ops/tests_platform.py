"""
Tests for the platform upgrade:
  • dynamic permission matrix (roles in the database, per-person grants, Admin-only permissions),
  • Designer workspace access derived from the same matrix,
  • account block / delete with last-Admin protection,
  • order book: stock reserved → dispatched → returned, forward-only status, public tracking,
  • product deletion keeps stock history; one-click zero stock,
  • system tools: Admin only, reset needs RESET + password and keeps accounts.

Run:  python manage.py test ops
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, override_settings

from catalog.models import Product
from storefront.models import BrandSettings, UiTranslation

from .inventory import adjust_stock
from .models import InventoryItem, Order, RoleDefinition, StaffProfile, StockMovement
from .orders import set_status
from .roles import Role, has_perm, user_permissions
from .tests import BaseCase, StudioClient, make_product, make_user

User = get_user_model()


class PermissionMatrixTests(BaseCase):
    def test_admin_edits_role_permissions_and_it_applies_immediately(self):
        clerk = make_user("clerk", Role.WAREHOUSE)
        self.assertFalse(has_perm(clerk, "accounting.view"))
        c = StudioClient()
        c.login_as(self.owner)
        r = c.jpatch(f"/api/staff/roles/{Role.WAREHOUSE}", {"permissions": ["orders.view", "accounting.view"]})
        self.assertEqual(r.status_code, 200, r.content)
        clerk = User.objects.get(pk=clerk.pk)
        self.assertTrue(has_perm(clerk, "accounting.view"))
        self.assertFalse(has_perm(clerk, "inventory.adjust"))  # removed

    def test_admin_only_permissions_can_never_be_delegated(self):
        c = StudioClient()
        c.login_as(self.owner)
        r = c.jpatch(f"/api/staff/roles/{Role.MARKETING}", {"permissions": ["orders.view", "staff.manage"]})
        self.assertEqual(r.status_code, 400)
        emp = make_user("emp", Role.MARKETING)
        r = c.jpatch(f"/api/staff/team/{emp.pk}", {"extra_permissions": ["system.maintain"]})
        self.assertEqual(r.status_code, 400)
        # Even a row written straight into the database can't grant them.
        RoleDefinition.objects.filter(key=Role.MARKETING).update(permissions=["staff.manage"])
        from .roles import forget_role_matrix

        forget_role_matrix()
        self.assertNotIn("staff.manage", user_permissions(User.objects.get(pk=emp.pk)))

    def test_extra_permission_lets_one_person_cover_another_role(self):
        emp = make_user("cover", Role.WAREHOUSE)
        c = StudioClient()
        c.login_as(self.owner)
        r = c.jpatch(f"/api/staff/team/{emp.pk}", {"extra_permissions": ["accounting.view"]})
        self.assertEqual(r.status_code, 200, r.content)
        c2 = StudioClient()
        c2.login_as(User.objects.get(pk=emp.pk))
        self.assertEqual(c2.get("/api/staff/accounting/summary").status_code, 200)

    def test_custom_role_create_and_delete(self):
        c = StudioClient()
        c.login_as(self.owner)
        r = c.jpost("/api/staff/roles", {"label": "Field sales", "permissions": ["orders.view", "orders.create"]})
        self.assertEqual(r.status_code, 200, r.content)
        key = r.json()["key"]
        self.assertEqual(key, "FIELD_SALES")
        u = make_user("fs", key)
        self.assertTrue(has_perm(u, "orders.create"))
        self.assertEqual(c.delete(f"/api/staff/roles/{key}", **c._h()).status_code, 400)  # still has people
        u.delete()
        self.assertEqual(c.delete(f"/api/staff/roles/{key}", **c._h()).status_code, 200)

    def test_designer_workspace_follows_the_matrix(self):
        des = make_user("des", Role.DESIGNER)
        des = User.objects.get(pk=des.pk)
        self.assertTrue(des.is_staff)
        self.assertTrue(des.has_perm("storefront.change_pagesection"))
        self.assertTrue(des.has_perm("catalog.change_product"))
        self.assertFalse(des.has_perm("catalog.delete_product"))
        self.assertFalse(des.has_perm("ops.view_invoice"))
        c = Client()
        c.force_login(des)
        from django.conf import settings

        self.assertEqual(c.get(f"/{settings.ADMIN_URL}storefront/pagesection/").status_code, 200)
        self.assertEqual(c.get(f"/{settings.ADMIN_URL}ops/invoice/").status_code, 403)
        # Taking site.design away closes the workspace.
        row = RoleDefinition.objects.get(key=Role.DESIGNER)
        row.permissions = ["orders.view"]
        row.save()
        self.assertFalse(User.objects.get(pk=des.pk).is_staff)


class AccountTests(BaseCase):
    def test_block_switches_the_account_off_and_restore_on(self):
        emp = make_user("emp", Role.WAREHOUSE)
        c = StudioClient()
        c.login_as(self.owner)
        self.assertEqual(c.jpatch(f"/api/staff/team/{emp.pk}", {"active": False}).status_code, 200)
        self.assertFalse(User.objects.get(pk=emp.pk).is_active)
        self.assertEqual(c.jpatch(f"/api/staff/team/{emp.pk}", {"active": True}).status_code, 200)
        self.assertTrue(User.objects.get(pk=emp.pk).is_active)

    def test_delete_account_keeps_their_history(self):
        emp = make_user("leaver", Role.WAREHOUSE)
        adjust_stock(self.item, "IN", 5, "Count", emp)
        c = StudioClient()
        c.login_as(self.owner)
        self.assertEqual(c.delete(f"/api/staff/team/{emp.pk}", **c._h()).status_code, 200)
        self.assertFalse(User.objects.filter(pk=emp.pk).exists())
        self.assertIsNone(StockMovement.objects.get().performed_by)

    def test_last_admin_is_protected(self):
        other = make_user("admin2", superuser=True)
        StaffProfile.objects.create(user=other, role=Role.SUPER_ADMIN)
        c = StudioClient()
        c.login_as(other)
        self.assertEqual(c.delete(f"/api/staff/team/{other.pk}", **c._h()).status_code, 400)  # not yourself
        self.assertEqual(c.delete(f"/api/staff/team/{self.owner.pk}", **c._h()).status_code, 200)  # another admin remains
        c2 = StudioClient()
        c2.login_as(make_user("x", Role.WAREHOUSE))
        self.assertEqual(c2.delete(f"/api/staff/team/{other.pk}", **c2._h()).status_code, 403)  # not an admin


class OrderBookTests(BaseCase):
    def setUp(self):
        super().setUp()
        adjust_stock(self.item, "IN", 10, "Opening", self.owner)
        self.field = make_user("field", Role.MARKETING)
        self.wh = make_user("wh", Role.WAREHOUSE)

    def log_order(self, qty=3, **extra):
        c = StudioClient()
        c.login_as(self.field)
        body = {"customer_name": "Asha Patil", "phone": "+91 98765 43210", "source": "FIELD",
                "lines": [{"product_id": self.product.pk, "quantity": qty, "unit_price": "90.00"}], **extra}
        return c.jpost("/api/staff/orders", body)

    def stock(self):
        i = InventoryItem.objects.get(pk=self.item.pk)
        return i.stock_quantity, i.reserved_quantity

    def test_status_flow_moves_stock_and_logs_it(self):
        r = self.log_order(3, shipping="50")
        self.assertEqual(r.status_code, 200, r.content)
        o = r.json()
        self.assertEqual(o["status"], "PENDING")
        self.assertEqual(Decimal(o["total"]), Decimal("320.00"))
        self.assertEqual(self.stock(), (10, 0))
        c = StudioClient()
        c.login_as(self.wh)
        url = f"/api/staff/orders/{o['id']}/status"
        self.assertEqual(c.jpost(url, {"status": "CONFIRMED"}).status_code, 200)
        self.assertEqual(self.stock(), (10, 3))  # reserved
        self.assertEqual(c.jpost(url, {"status": "IN_TRANSIT", "courier": "DTDC"}).status_code, 200)
        self.assertEqual(self.stock(), (7, 0))  # left the building
        self.assertEqual(c.jpost(url, {"status": "CONFIRMED"}).status_code, 400)  # forward only
        self.assertEqual(c.jpost(url, {"status": "CANCELLED"}).status_code, 200)
        self.assertEqual(self.stock(), (10, 0))  # returned
        self.assertEqual(c.jpost(url, {"status": "DELIVERED"}).status_code, 400)  # cancelled is final
        self.assertEqual(StockMovement.objects.filter(reason__contains=o["number"]).count(), 3)  # reserve, dispatch, return

    def test_cannot_reserve_more_than_available(self):
        o = self.log_order(30).json()
        c = StudioClient()
        c.login_as(self.wh)
        r = c.jpost(f"/api/staff/orders/{o['id']}/status", {"status": "CONFIRMED"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.stock(), (10, 0))
        self.assertEqual(Order.objects.get(pk=o["id"]).status, "PENDING")

    def test_marketing_can_log_but_not_move_orders(self):
        o = self.log_order().json()
        c = StudioClient()
        c.login_as(self.field)
        self.assertEqual(c.jpost(f"/api/staff/orders/{o['id']}/status", {"status": "CONFIRMED"}).status_code, 403)
        self.assertEqual(self.log_order(status="DELIVERED").status_code, 403)

    def test_walk_in_sale_logged_as_delivered_takes_stock_out(self):
        c = StudioClient()
        c.login_as(self.owner)
        r = c.jpost("/api/staff/orders", {"customer_name": "Walk-in", "phone": "9876543210", "source": "WALK_IN",
                                          "status": "DELIVERED",
                                          "lines": [{"product_id": self.product.pk, "quantity": 2, "unit_price": "90"}]})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.stock(), (8, 0))

    def test_customer_tracking_needs_number_and_matching_phone(self):
        o = self.log_order().json()
        pub = Client()
        r = pub.get("/api/orders/track", {"number": o["number"], "phone": "98765-43210"})
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual(body["status"], "PENDING")
        self.assertNotIn("internal_notes", body)
        self.assertNotIn("phone", body)
        self.assertEqual(pub.get("/api/orders/track", {"number": o["number"], "phone": "9999999999"}).status_code, 404)
        token = body["token"]
        self.assertEqual(pub.get(f"/api/orders/track/{token}").status_code, 200)
        receipt = pub.get(f"/api/orders/track/{token}/receipt?size=thermal")
        self.assertEqual(receipt.status_code, 200)
        self.assertIn(o["number"], receipt.content.decode())
        self.assertNotIn("98765", receipt.content.decode())  # no phone number on the public receipt

    def test_staff_receipt_prints_the_brand_name(self):
        b = BrandSettings.load()
        b.brand_name = "Nila Naturals"
        b.save()
        o = self.log_order().json()
        c = StudioClient()
        c.login_as(self.field)
        html = c.get(f"/api/staff/orders/{o['id']}/receipt").content.decode()
        self.assertIn("Nila Naturals", html)
        self.assertIn("Print / Save as PDF", html)


class CatalogControlTests(BaseCase):
    def test_deleting_a_product_keeps_stock_history(self):
        adjust_stock(self.item, "IN", 5, "Count", self.owner)
        c = StudioClient()
        c.login_as(self.owner)
        r = c.delete(f"/api/staff/catalog/products/{self.product.pk}", **c._h())
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
        mv = StockMovement.objects.get()
        self.assertIsNone(mv.item_id)
        self.assertIn("Test Brush", mv.item_label)

    def test_designer_cannot_delete_products_by_default(self):
        c = StudioClient()
        c.login_as(make_user("des", Role.DESIGNER))
        self.assertEqual(c.delete(f"/api/staff/catalog/products/{self.product.pk}", **c._h()).status_code, 403)

    def test_zero_stock_is_one_logged_correction(self):
        adjust_stock(self.item, "IN", 12, "Count", self.owner)
        c = StudioClient()
        c.login_as(make_user("inv", Role.INVENTORY_MANAGER))
        r = c.jpost(f"/api/staff/inventory/items/{self.item.pk}/zero")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(InventoryItem.objects.get(pk=self.item.pk).stock_quantity, 0)
        self.assertEqual(StockMovement.objects.filter(kind="ADJUSTMENT", quantity=-12).count(), 1)

    def test_category_with_products_needs_a_decision(self):
        c = StudioClient()
        c.login_as(self.owner)
        cat = self.product.category
        self.assertEqual(c.delete(f"/api/staff/catalog/categories/{cat.pk}", **c._h()).status_code, 400)
        new = c.jpost("/api/staff/catalog/categories", {"name": "Pastes"}).json()
        self.assertEqual(c.delete(f"/api/staff/catalog/categories/{cat.pk}?move_to={new['id']}", **c._h()).status_code, 200)
        self.assertEqual(Product.objects.get(pk=self.product.pk).category_id, new["id"])


@override_settings(FRONTEND_DIST=__import__("pathlib").Path(__file__).resolve().parent)
class SystemToolTests(BaseCase):
    def test_only_admin_can_use_system_tools(self):
        c = StudioClient()
        c.login_as(make_user("w", Role.WAREHOUSE))
        self.assertEqual(c.jpost("/api/staff/system/clear-cache").status_code, 403)
        c2 = StudioClient()
        c2.login_as(self.owner)
        self.assertEqual(c2.jpost("/api/staff/system/clear-cache").status_code, 200)
        r = c2.jpost("/api/staff/system/recover")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["ok"], r.json())
        self.assertTrue(c2.get("/api/staff/system/health").json()["database"])

    def test_reset_needs_reset_and_password_and_keeps_accounts(self):
        import tempfile
        from pathlib import Path

        UiTranslation.objects.create(language="hi", key="search.placeholder", text="खोजें")
        emp = make_user("keepme", Role.WAREHOUSE)
        c = StudioClient()
        c.login_as(self.owner)
        self.assertEqual(c.jpost("/api/staff/system/reset", {"confirm": "reset", "password": "pw-123456!"}).status_code, 400)
        self.assertEqual(c.jpost("/api/staff/system/reset", {"confirm": "RESET", "password": "wrong"}).status_code, 403)
        with tempfile.TemporaryDirectory() as tmp, override_settings(BASE_DIR=Path(tmp)):
            r = c.jpost("/api/staff/system/reset", {"confirm": "RESET", "password": "pw-123456!"})
            self.assertEqual(r.status_code, 200, r.content)
            self.assertTrue(any(Path(tmp, "backups").glob("*.json")))
        self.assertFalse(Product.objects.exists())
        self.assertFalse(UiTranslation.objects.exists())
        self.assertTrue(User.objects.filter(pk=emp.pk).exists())
        self.assertEqual(StaffProfile.objects.get(user=emp).role, Role.WAREHOUSE)
        self.assertEqual(BrandSettings.load().brand_name, "")
        cache.clear()
