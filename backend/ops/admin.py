"""
Operations in the admin (super admins only — employees use Paalvi Studio at /studio).

Stock numbers are read-only here on purpose: every change must go through the Studio so it
is locked, logged in the movement audit trail and re-checked for alerts.
"""

from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display

from .models import (
    Expense,
    InventoryAlert,
    InventoryItem,
    InventorySettings,
    Invoice,
    InvoiceLine,
    PaymentRecord,
    ProductionBatch,
    StaffProfile,
    StockMovement,
)


def studio_link(tab, label="Open in Studio ↗"):
    return format_html('<a href="{}/studio/{}" target="_blank" rel="noopener" class="text-primary-600 font-semibold">{}</a>',
                       settings.SITE_URL, tab, label)


@admin.register(StaffProfile)
class StaffProfileAdmin(ModelAdmin):
    list_display = ["user", "full_name", "role", "is_active", "last_login"]
    list_editable = ["role", "is_active"]
    list_filter = ["role", "is_active"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "user__email"]
    autocomplete_fields = ["user"]

    @display(description="Name")
    def full_name(self, obj):
        return obj.user.get_full_name() or "—"

    @display(description="Last login")
    def last_login(self, obj):
        return obj.user.last_login or "Never"


@admin.register(InventorySettings)
class InventorySettingsAdmin(ModelAdmin):
    def has_add_permission(self, request):
        return not InventorySettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class AlertInline(TabularInline):
    model = InventoryAlert
    extra = 0
    fields = ["kind", "message", "is_active", "raised_at", "resolved_at"]
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(InventoryItem)
class InventoryItemAdmin(ModelAdmin):
    list_display = ["sku", "product", "variant", "stock_quantity", "reserved_quantity", "available_now", "low_stock_threshold",
                    "reorder_point", "expiry_date", "flags"]
    list_filter = ["product__category"]
    search_fields = ["sku", "product__title", "batch_number"]
    readonly_fields = ["stock_quantity", "reserved_quantity", "studio"]
    autocomplete_fields = ["product"]
    raw_id_fields = ["variant"]
    inlines = [AlertInline]
    list_select_related = ["product", "variant"]

    @display(description="Available")
    def available_now(self, obj):
        return obj.available

    @display(description="Alerts")
    def flags(self, obj):
        kinds = [a.get_kind_display() for a in obj.alerts.all() if a.is_active]
        return ", ".join(kinds) or "—"

    @display(description="Change stock")
    def studio(self, obj):
        return studio_link("inventory", "Adjust stock in Studio ↗ (every change is logged)")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("alerts")


@admin.register(StockMovement)
class StockMovementAdmin(ModelAdmin):
    list_display = ["created_at", "item", "kind", "quantity", "stock_after", "reason", "performed_by"]
    list_filter = ["kind", ("created_at", admin.DateFieldListFilter)]
    search_fields = ["item__sku", "item__product__title", "reason"]
    list_select_related = ["item__product", "performed_by"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProductionBatch)
class ProductionBatchAdmin(ModelAdmin):
    list_display = ["batch_code", "item", "status", "planned_quantity", "completed_quantity", "assigned_to", "expected_completion_date"]
    list_filter = ["status"]
    search_fields = ["batch_code", "item__sku", "item__product__title"]
    readonly_fields = ["batch_code", "status", "completed_quantity", "completed_at", "item", "studio"]
    raw_id_fields = ["assigned_to"]
    exclude = ["created_by"]

    @display(description="Stages")
    def studio(self, obj):
        return studio_link("production", "Move stages in Studio ↗")

    def has_add_permission(self, request):
        return False


class LineInline(TabularInline):
    model = InvoiceLine
    extra = 0
    fields = ["description", "hsn", "quantity", "unit_price", "gst_rate", "taxable_value", "tax_amount"]
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class PaymentInline(TabularInline):
    model = PaymentRecord
    extra = 0
    fields = ["paid_on", "amount", "mode", "reference_id", "recorded_by"]
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Invoice)
class InvoiceAdmin(ModelAdmin):
    list_display = ["number", "issue_date", "customer_name", "channel", "total", "amount_paid", "payment_status"]
    list_filter = ["payment_status", "channel"]
    search_fields = ["number", "customer_name", "customer_gstin"]
    inlines = [LineInline, PaymentInline]
    readonly_fields = ["number", "subtotal", "cgst", "sgst", "igst", "total", "amount_paid", "payment_status", "studio"]
    exclude = ["created_by"]
    raw_id_fields = ["lead"]

    @display(description="Payments")
    def studio(self, obj):
        return studio_link("accounting", "Record payments in Studio ↗")

    def has_add_permission(self, request):
        return False


@admin.register(Expense)
class ExpenseAdmin(ModelAdmin):
    list_display = ["spent_on", "category", "vendor", "amount", "gst_amount"]
    list_filter = ["category"]
    search_fields = ["vendor", "description"]
    exclude = ["recorded_by", "receipt"]
