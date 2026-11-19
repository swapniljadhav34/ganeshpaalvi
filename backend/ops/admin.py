"""
Operations in the admin (Admin only — everyone else uses Studio at /studio).
People, roles and permissions are managed in ONE place: Studio → Team & roles. The screens
here are a read-mostly fallback for the Admin.

Stock numbers are read-only here on purpose: every change must go through the Studio so it
is locked, logged in the movement audit trail and re-checked for alerts.
"""

from django import forms
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
    Order,
    OrderEvent,
    OrderLine,
    PaymentRecord,
    ProductionBatch,
    RoleDefinition,
    StaffProfile,
    StockMovement,
)
from .roles import role_matrix


def studio_link(tab, label="Open in Studio ↗"):
    return format_html('<a href="{}/studio/{}" target="_blank" rel="noopener" class="text-primary-600 font-semibold">{}</a>',
                       settings.STAFF_URL, tab, label)


class StaffProfileForm(forms.ModelForm):
    role = forms.ChoiceField()

    class Meta:
        model = StaffProfile
        fields = ["user", "role", "kind", "company", "phone", "city", "is_active"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["role"].choices = [(k, r.label) for k, r in role_matrix().items()]


@admin.register(StaffProfile)
class StaffProfileAdmin(ModelAdmin):
    form = StaffProfileForm
    list_display = ["user", "full_name", "role_name", "kind", "is_active", "last_login", "studio"]
    list_filter = ["kind", "is_active"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "user__email", "company"]
    autocomplete_fields = ["user"]

    @display(description="Name")
    def full_name(self, obj):
        return obj.user.get_full_name() or obj.company or "—"

    @display(description="Role")
    def role_name(self, obj):
        r = role_matrix().get(obj.role)
        return r.label if r else obj.role

    @display(description="Last login")
    def last_login(self, obj):
        return obj.user.last_login or "Never"

    @display(description="")
    def studio(self, obj):
        return studio_link("team", "Permissions in Studio ↗")


@admin.register(RoleDefinition)
class RoleDefinitionAdmin(ModelAdmin):
    list_display = ["label", "key", "description", "perm_count", "is_builtin", "studio"]
    readonly_fields = ["key", "permissions", "is_builtin"]

    @display(description="Permissions")
    def perm_count(self, obj):
        return len(obj.permissions or [])

    @display(description="")
    def studio(self, obj):
        return studio_link("team", "Edit the permission matrix in Studio ↗")

    def has_add_permission(self, request):
        return False  # roles are created in Studio, where the permission matrix is


class OrderLineInline(TabularInline):
    model = OrderLine
    extra = 0
    fields = ["title", "sku", "quantity", "unit_price"]
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class OrderEventInline(TabularInline):
    model = OrderEvent
    extra = 0
    fields = ["at", "status", "note", "by"]
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ["number", "created_at", "customer_name", "phone", "source", "status", "total", "payment_status"]
    list_filter = ["status", "source", "channel", "payment_status"]
    search_fields = ["number", "customer_name", "phone", "business_name"]
    inlines = [OrderLineInline, OrderEventInline]
    readonly_fields = ["number", "tracking_token", "status", "stock_state", "subtotal", "total", "studio"]
    exclude = ["created_by", "lead", "assigned_to"]

    @display(description="Status")
    def studio(self, obj):
        return studio_link("orders", "Change status in Studio ↗ (keeps stock in step)")

    def has_add_permission(self, request):
        return False


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
