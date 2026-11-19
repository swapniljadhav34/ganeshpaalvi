"""
Operations data: staff roles, inventory (with an audit log and automatic alerts),
production batches, accounting (GST invoices, payments, expenses) and website traffic.

Stock numbers are NEVER edited directly: every change goes through ops.inventory.adjust_stock(),
which locks the row, updates it with F() expressions inside a transaction and writes a
StockMovement. That's why the stock fields are read-only in the admin.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from storefront import validators as V
from storefront.utils import SingletonModel

from .roles import Role

User = settings.AUTH_USER_MODEL


def private_storage():
    """Receipts live outside /media/ and are only downloadable through a permission check.

    On hosts without a permanent disk set S3_PRIVATE_BUCKET_NAME: receipts then go to that
    separate, non-public bucket (never the public media bucket).
    """
    bucket = getattr(settings, "S3_PRIVATE_BUCKET_NAME", "")
    if bucket:
        from storages.backends.s3 import S3Storage

        return S3Storage(bucket_name=bucket, endpoint_url=settings.S3_ENDPOINT_URL or None,
                         access_key=settings.S3_ACCESS_KEY_ID, secret_key=settings.S3_SECRET_ACCESS_KEY,
                         default_acl="private", querystring_auth=True, file_overwrite=False, custom_domain=None)
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)


# ---------------------------------------------------------------------------
# People, roles and the permission matrix
# ---------------------------------------------------------------------------
class RoleDefinition(models.Model):
    """One role and the permissions it grants. Built-in roles are seeded; the Admin can add more."""

    key = models.CharField(max_length=40, unique=True, help_text="Internal code, e.g. FIELD_SALES. Can't be changed later.")
    label = models.CharField(max_length=60, help_text="Name people see, e.g. 'Field sales'.")
    description = models.CharField(max_length=200, blank=True)
    permissions = models.JSONField(default=list, blank=True)
    is_builtin = models.BooleanField(default=False, editable=False)
    order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["order", "label"]
        verbose_name = "Role"

    def __str__(self):
        return self.label

    def clean(self):
        from .roles import GRANTABLE, PERMISSIONS

        unknown = set(self.permissions or []) - set(PERMISSIONS)
        if unknown:
            raise ValidationError(f"Unknown permission(s): {', '.join(sorted(unknown))}")
        if self.key != Role.SUPER_ADMIN and set(self.permissions or []) - GRANTABLE:
            raise ValidationError("Account management and system maintenance stay with the Admin role only.")

    def save(self, *args, **kwargs):
        from .roles import GRANTABLE, PERMISSIONS, forget_role_matrix

        if self.key == Role.SUPER_ADMIN:
            self.permissions = sorted(PERMISSIONS)
        else:
            self.permissions = sorted(set(self.permissions or []) & GRANTABLE)
        super().save(*args, **kwargs)
        forget_role_matrix()
        for prof in StaffProfile.objects.filter(role=self.key).select_related("user"):
            prof.sync_user_flags()

    def delete(self, *args, **kwargs):
        from .roles import forget_role_matrix

        if self.is_builtin:
            raise ValidationError("Built-in roles can't be deleted. Change their permissions instead.")
        if StaffProfile.objects.filter(role=self.key).exists():
            raise ValidationError("Move the people in this role to another role first.")
        out = super().delete(*args, **kwargs)
        forget_role_matrix()
        return out


class StaffProfile(models.Model):
    class Kind(models.TextChoices):
        EMPLOYEE = "EMPLOYEE", "Internal employee"
        WAREHOUSE = "WAREHOUSE", "Warehouse"
        DISTRIBUTION = "DISTRIBUTION", "Distribution"
        MARKETING = "MARKETING", "Marketing / field"
        VENDOR = "VENDOR", "External vendor"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff_profile")
    role = models.CharField(max_length=40, default=Role.EMPLOYEE_OPS,
                            help_text="Decides what this person can open. 'Admin' has master control.")
    extra_permissions = models.JSONField(default=list, blank=True,
                                         help_text="Extra permissions for this person only (e.g. covering a colleague's work).")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.EMPLOYEE, verbose_name="Directory group")
    company = models.CharField(max_length=120, blank=True, help_text="Vendors: company name.")
    phone = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True, help_text="Untick to block access without deleting the account.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Person & role"
        verbose_name_plural = "People & roles"

    def __str__(self):
        from .roles import role_info

        r = role_info(self.role)
        return f"{self.user.get_username()} - {r.label if r else self.role}"

    def clean(self):
        from .roles import GRANTABLE, role_info

        if role_info(self.role) is None:
            raise ValidationError("Choose a role that exists.")
        if set(self.extra_permissions or []) - GRANTABLE:
            raise ValidationError("Account management and system maintenance stay with the Admin role only.")
        losing_admin = self.user_id and self.user.is_superuser and (self.role != Role.SUPER_ADMIN or not self.is_active)
        if losing_admin and not other_admins(self.user_id).exists():
            raise ValidationError("This is the last Admin. Make someone else an Admin first.")

    def sync_user_flags(self):
        """Keep Django's flags in step with the matrix (one source of truth).

        is_superuser: only an active Admin.  is_staff: anyone allowed into the Designer workspace.
        """
        from .roles import role_info, wants_designer_access

        user = self.user
        r = role_info(self.role)
        perms = set(r.permissions if r else ()) | set(self.extra_permissions or [])
        want_super = self.is_active and self.role == Role.SUPER_ADMIN
        want_staff = want_super or (self.is_active and wants_designer_access(perms))
        if user.is_superuser != want_super or user.is_staff != want_staff:
            user.is_superuser, user.is_staff = want_super, want_staff
            user.save(update_fields=["is_superuser", "is_staff"])

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.sync_user_flags()


def other_admins(exclude_user_id):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(is_superuser=True, is_active=True).exclude(pk=exclude_user_id)


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------
class InventorySettings(SingletonModel):
    expiry_warning_days = models.PositiveSmallIntegerField(default=60, validators=[MinValueValidator(1), MaxValueValidator(365)],
                                                           help_text="Raise an 'Expiring soon' alert this many days before expiry.")
    default_low_stock_threshold = models.PositiveIntegerField(default=20, help_text="Used for new stock items.")
    default_reorder_point = models.PositiveIntegerField(default=40, help_text="Used for new stock items.")
    sync_storefront_status = models.BooleanField(
        default=True, help_text="Update the website's 'In stock / Low stock / Out of stock' label automatically when stock changes.")

    class Meta:
        verbose_name = verbose_name_plural = "Inventory settings"

    def __str__(self):
        return "Inventory settings"


class InventoryItem(models.Model):
    """One stock-keeping unit: a product, or one variant of a product."""

    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="inventory_items")
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.CASCADE, null=True, blank=True,
                                related_name="inventory_items", help_text="Empty = stock for the product as a whole.")
    sku = models.CharField(max_length=60, unique=True, verbose_name="SKU")
    stock_quantity = models.IntegerField(default=0, help_text="Pieces physically in stock. Changed only through stock movements.")
    reserved_quantity = models.IntegerField(default=0, help_text="Pieces promised to pending retail/wholesale orders.")
    low_stock_threshold = models.PositiveIntegerField(default=20)
    reorder_point = models.PositiveIntegerField(default=40, help_text="Below this, production should be planned.")
    batch_number = models.CharField(max_length=40, blank=True, help_text="Current lot / batch code on the shelf.")
    expiry_date = models.DateField(null=True, blank=True, db_index=True, help_text="Expiry of the current batch.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sku"]
        verbose_name = "Stock item"
        constraints = [
            models.CheckConstraint(condition=Q(stock_quantity__gte=0), name="inv_stock_not_negative"),
            models.CheckConstraint(condition=Q(reserved_quantity__gte=0), name="inv_reserved_not_negative"),
            models.UniqueConstraint(fields=["product"], condition=Q(variant__isnull=True), name="inv_one_item_per_product"),
            models.UniqueConstraint(fields=["product", "variant"], condition=Q(variant__isnull=False), name="inv_one_item_per_variant"),
        ]

    def __str__(self):
        return f"{self.sku} — {self.label}"

    @property
    def label(self):
        return f"{self.product.title} · {self.variant.value}" if self.variant_id else self.product.title

    @property
    def available(self):
        return self.stock_quantity - self.reserved_quantity

    # Stock numbers are written ONLY by ops.inventory.adjust_stock (locked UPDATE + movement log).
    # A normal save() never touches them, so a stale copy (e.g. an admin form left open) can't overwrite stock.
    PROTECTED_FIELDS = ("stock_quantity", "reserved_quantity")

    def save(self, *args, **kwargs):
        if not self._state.adding and kwargs.get("update_fields") is None:
            kwargs["update_fields"] = [f.name for f in self._meta.concrete_fields
                                       if not f.primary_key and f.name not in self.PROTECTED_FIELDS]
        super().save(*args, **kwargs)


class StockMovement(models.Model):
    class Kind(models.TextChoices):
        IN = "IN", "Stock in (purchase / return)"
        OUT = "OUT", "Stock out (sale)"
        PRODUCTION_IN = "PRODUCTION_IN", "Production completed"
        ADJUSTMENT = "ADJUSTMENT", "Stock count correction"
        DAMAGED = "DAMAGED", "Damaged / expired write-off"
        WHOLESALE_DISPATCH = "WHOLESALE_DISPATCH", "Wholesale dispatch"
        RESERVE = "RESERVE", "Reserved for an order"
        RELEASE = "RELEASE", "Reservation released"

    # SET_NULL: deleting a product keeps its history; item_label remembers what it was.
    item = models.ForeignKey(InventoryItem, on_delete=models.SET_NULL, null=True, related_name="movements")
    item_label = models.CharField(max_length=220, blank=True, help_text="SKU and name at the time (kept if the product is deleted).")
    kind = models.CharField(max_length=20, choices=Kind.choices, db_index=True)
    quantity = models.IntegerField(help_text="Change in pieces: positive adds, negative removes.")
    stock_after = models.IntegerField()
    reserved_after = models.IntegerField()
    reason = models.CharField(max_length=300)
    batch_number = models.CharField(max_length=40, blank=True)
    production_batch = models.ForeignKey("ProductionBatch", on_delete=models.SET_NULL, null=True, blank=True, related_name="movements")
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="stock_movements")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "Stock movement"
        indexes = [models.Index(fields=["item", "-created_at"], name="mv_item_recent")]

    def __str__(self):
        return f"{self.get_kind_display()} {self.quantity:+d} · {self.item.sku if self.item_id else self.item_label}"

    def save(self, *args, **kwargs):
        if not self.item_label and self.item_id:
            self.item_label = f"{self.item.sku} - {self.item.label}"[:220]
        if self.pk:
            raise ValidationError("Stock movements are a permanent audit log and can't be edited.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Stock movements are a permanent audit log and can't be deleted.")


class InventoryAlert(models.Model):
    class Kind(models.TextChoices):
        OUT_OF_STOCK = "OUT_OF_STOCK", "Out of stock"
        LOW_STOCK = "LOW_STOCK", "Low stock"
        EXPIRING_SOON = "EXPIRING_SOON", "Expiring soon"
        PRODUCTION_NEEDED = "PRODUCTION_NEEDED", "Production needed"

    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="alerts")
    kind = models.CharField(max_length=20, choices=Kind.choices, db_index=True)
    message = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True, db_index=True)
    raised_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-raised_at"]
        verbose_name = "Inventory alert"
        constraints = [
            models.UniqueConstraint(fields=["item", "kind"], condition=Q(is_active=True), name="inv_one_active_alert_per_kind"),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.item.sku}"


# ---------------------------------------------------------------------------
# Production
# ---------------------------------------------------------------------------
class ProductionBatch(models.Model):
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planned"
        RAW_MATERIALS_READY = "RAW_MATERIALS_READY", "Raw materials ready"
        IN_PRODUCTION = "IN_PRODUCTION", "In production"
        QC_TESTING = "QC_TESTING", "QC testing"
        PACKAGING = "PACKAGING", "Packaging"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    FLOW = [Status.PLANNED, Status.RAW_MATERIALS_READY, Status.IN_PRODUCTION, Status.QC_TESTING, Status.PACKAGING, Status.COMPLETED]
    ACTIVE = FLOW[:-1]  # everything before COMPLETED

    batch_code = models.CharField(max_length=30, unique=True)
    item = models.ForeignKey(InventoryItem, on_delete=models.SET_NULL, null=True, related_name="production_batches")
    item_label = models.CharField(max_length=220, blank=True, help_text="Product at the time (kept if the product is deleted).")
    planned_quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    completed_quantity = models.PositiveIntegerField(default=0)
    wastage_quantity = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PLANNED, db_index=True)
    start_date = models.DateField(default=timezone.localdate)
    expected_completion_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True, help_text="Expiry of the goods this batch produces.")
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="production_batches")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Production batch"
        verbose_name_plural = "Production batches"

    def __str__(self):
        return f"{self.batch_code} · {self.item.sku if self.item_id else self.item_label}"

    def save(self, *args, **kwargs):
        if self.item_id and not self.item_label:
            self.item_label = f"{self.item.sku} - {self.item.label}"[:220]
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Accounting (super admin & accountant only)
# ---------------------------------------------------------------------------
MONEY = {"max_digits": 12, "decimal_places": 2, "default": Decimal("0.00")}


class InvoiceSequence(models.Model):
    """Gap-free invoice numbers per Indian financial year (April–March)."""

    financial_year = models.CharField(max_length=7, unique=True)  # e.g. 2026-27
    last_number = models.PositiveIntegerField(default=0)


class Invoice(models.Model):
    class Channel(models.TextChoices):
        RETAIL = "retail", "Retail"
        WHOLESALE = "wholesale", "Wholesale"

    class TaxMode(models.TextChoices):
        INTRA = "intra", "Within state (CGST + SGST)"
        INTER = "inter", "Other state (IGST)"

    class PaymentStatus(models.TextChoices):
        UNPAID = "UNPAID", "Unpaid"
        PARTIAL = "PARTIAL", "Partly paid"
        PAID = "PAID", "Paid"
        OVERDUE = "OVERDUE", "Overdue"

    number = models.CharField(max_length=30, unique=True)
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.WHOLESALE, db_index=True)
    lead = models.ForeignKey("leads.LeadInquiry", on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    customer_name = models.CharField(max_length=140)
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_gstin = models.CharField(max_length=15, blank=True, verbose_name="Customer GSTIN")
    billing_address = models.TextField(blank=True)
    place_of_supply = models.CharField(max_length=60, blank=True, help_text="State, e.g. Maharashtra.")
    tax_mode = models.CharField(max_length=5, choices=TaxMode.choices, default=TaxMode.INTRA)
    prices_include_tax = models.BooleanField(default=False, help_text="Tick if line prices already include GST (typical for retail).")
    issue_date = models.DateField(default=timezone.localdate, db_index=True)
    due_date = models.DateField(db_index=True)
    subtotal = models.DecimalField(**MONEY)
    cgst = models.DecimalField(**MONEY)
    sgst = models.DecimalField(**MONEY)
    igst = models.DecimalField(**MONEY)
    total = models.DecimalField(**MONEY)
    amount_paid = models.DecimalField(**MONEY)
    payment_status = models.CharField(max_length=8, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID, db_index=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issue_date", "-pk"]
        indexes = [models.Index(fields=["payment_status", "due_date"], name="inv_status_due")]

    def __str__(self):
        return f"{self.number} · {self.customer_name}"

    @property
    def balance(self):
        return self.total - self.amount_paid

    @property
    def tax_total(self):
        return self.cgst + self.sgst + self.igst


GST_RATES = [(Decimal("0"), "0%"), (Decimal("5"), "5%"), (Decimal("12"), "12%"), (Decimal("18"), "18%"), (Decimal("28"), "28%")]


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    description = models.CharField(max_length=200)
    hsn = models.CharField(max_length=10, blank=True, verbose_name="HSN")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("18"))
    taxable_value = models.DecimalField(**MONEY)
    tax_amount = models.DecimalField(**MONEY)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return self.description


class PaymentRecord(models.Model):
    class Mode(models.TextChoices):
        UPI = "UPI", "UPI"
        BANK = "BANK", "Bank transfer"
        CASH = "CASH", "Cash"
        CARD = "CARD", "Card"

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    mode = models.CharField(max_length=5, choices=Mode.choices)
    reference_id = models.CharField(max_length=80, blank=True, help_text="UPI / bank reference number.")
    paid_on = models.DateField(default=timezone.localdate, db_index=True)
    notes = models.CharField(max_length=200, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_on", "-pk"]

    def __str__(self):
        return f"₹{self.amount} {self.mode} → {self.invoice.number}"


class Expense(models.Model):
    class Category(models.TextChoices):
        RAW_MATERIALS = "RAW_MATERIALS", "Raw materials"
        PACKAGING = "PACKAGING", "Packaging"
        SHIPPING = "SHIPPING", "Shipping"
        UTILITIES = "UTILITIES", "Utilities"
        PAYROLL = "PAYROLL", "Payroll"
        MARKETING = "MARKETING", "Marketing"
        OTHER = "OTHER", "Other"

    category = models.CharField(max_length=14, choices=Category.choices, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))],
                                 help_text="Total paid, including GST.")
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"),
                                     help_text="GST included in the amount (input tax credit).")
    vendor = models.CharField(max_length=140)
    vendor_gstin = models.CharField(max_length=15, blank=True, verbose_name="Vendor GSTIN")
    spent_on = models.DateField(default=timezone.localdate, db_index=True)
    description = models.CharField(max_length=240, blank=True)
    receipt = models.FileField(upload_to="receipts/%Y/%m/", storage=private_storage, blank=True, validators=V.RECEIPT)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-spent_on", "-pk"]

    def __str__(self):
        return f"{self.get_category_display()} ₹{self.amount} · {self.vendor}"


# ---------------------------------------------------------------------------
# First-party traffic analytics (no cookies, no personal data)
# ---------------------------------------------------------------------------
class TrafficEvent(models.Model):
    class Kind(models.TextChoices):
        PAGEVIEW = "pageview", "Page view"
        PRODUCT = "product", "Product view"

    class Device(models.TextChoices):
        MOBILE = "mobile", "Mobile"
        TABLET = "tablet", "Tablet"
        DESKTOP = "desktop", "Desktop"

    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.PAGEVIEW)
    path = models.CharField(max_length=200)
    product = models.ForeignKey("catalog.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    category_slug = models.CharField(max_length=100, blank=True)
    referrer_host = models.CharField(max_length=120, blank=True)
    device = models.CharField(max_length=8, choices=Device.choices)
    tier = models.CharField(max_length=10, default="retail")
    session_hash = models.CharField(max_length=16, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["product", "created_at"], name="traffic_product_time")]


# ---------------------------------------------------------------------------
# Order book (online + offline orders) with live status
# ---------------------------------------------------------------------------
class Order(models.Model):
    class Source(models.TextChoices):
        ONLINE = "ONLINE", "Website"
        PHONE = "PHONE", "Phone call"
        WHATSAPP = "WHATSAPP", "WhatsApp"
        FIELD = "FIELD", "Field visit (marketing / distribution)"
        WALK_IN = "WALK_IN", "Walk-in / showroom"
        EMAIL = "EMAIL", "Email"

    class Channel(models.TextChoices):
        RETAIL = "RETAIL", "Retail"
        WHOLESALE = "WHOLESALE", "Wholesale"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        PACKED = "PACKED", "Packed"
        IN_TRANSIT = "IN_TRANSIT", "In transit"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    class Payment(models.TextChoices):
        UNPAID = "UNPAID", "Not paid"
        PARTIAL = "PARTIAL", "Part paid"
        PAID = "PAID", "Paid"
        COD = "COD", "Cash on delivery"

    class StockState(models.TextChoices):
        NONE = "NONE", "Not touched"
        RESERVED = "RESERVED", "Reserved"
        DISPATCHED = "DISPATCHED", "Taken out of stock"
        RETURNED = "RETURNED", "Returned to stock"

    FLOW = [Status.PENDING, Status.CONFIRMED, Status.PACKED, Status.IN_TRANSIT, Status.DELIVERED]

    number = models.CharField(max_length=24, unique=True)
    tracking_token = models.CharField(max_length=24, unique=True, help_text="Secret part of the customer's tracking link.")
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.PHONE, db_index=True)
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.RETAIL)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    stock_state = models.CharField(max_length=10, choices=StockState.choices, default=StockState.NONE)

    customer_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, db_index=True)
    email = models.EmailField(blank=True)
    business_name = models.CharField(max_length=140, blank=True)
    gstin = models.CharField(max_length=15, blank=True, verbose_name="GSTIN")
    address = models.TextField(blank=True)
    city = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=60, blank=True)
    pincode = models.CharField(max_length=10, blank=True)

    subtotal = models.DecimalField(**MONEY)
    discount = models.DecimalField(**MONEY)
    shipping = models.DecimalField(**MONEY)
    total = models.DecimalField(**MONEY)
    payment_status = models.CharField(max_length=8, choices=Payment.choices, default=Payment.UNPAID)
    payment_mode = models.CharField(max_length=40, blank=True, help_text="UPI, cash, bank transfer…")

    courier = models.CharField(max_length=80, blank=True)
    tracking_number = models.CharField(max_length=80, blank=True)
    expected_delivery = models.DateField(null=True, blank=True)

    customer_note = models.CharField(max_length=500, blank=True, help_text="Shown on the receipt and tracking page.")
    internal_notes = models.TextField(blank=True, help_text="Only staff see this.")
    lead = models.ForeignKey("leads.LeadInquiry", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders_logged")
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders_assigned")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["status", "-created_at"], name="order_status_recent")]

    def __str__(self):
        return f"{self.number} · {self.customer_name}"


class OrderLine(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    item = models.ForeignKey(InventoryItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    title = models.CharField(max_length=220)
    sku = models.CharField(max_length=60, blank=True)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Per piece, incl. GST.")

    class Meta:
        ordering = ["pk"]

    @property
    def line_total(self):
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))


class OrderEvent(models.Model):
    """Timeline of an order. Customer-visible events show on the tracking page."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=12, choices=Order.Status.choices)
    note = models.CharField(max_length=300, blank=True)
    by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["at", "pk"]
