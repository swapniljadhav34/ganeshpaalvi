"""Leads & Enquiries admin: a simple sales pipeline with filters and Excel export."""

from django.contrib import admin, messages
from django.utils.html import format_html
from import_export import fields, resources
from import_export.admin import ExportMixin
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import RangeDateFilter
from unfold.contrib.import_export.forms import ExportForm
from unfold.decorators import display

from .models import LeadInquiry


class LeadResource(resources.ModelResource):
    product = fields.Field(attribute="product__title", column_name="product")
    variant = fields.Field(attribute="variant__value", column_name="variant")
    package = fields.Field(attribute="package__name", column_name="package")

    class Meta:
        model = LeadInquiry
        fields = ["created_at", "name", "phone", "email", "business_name", "buyer_type", "city", "product", "variant",
                  "package", "tier", "quantity", "source", "status", "message", "notes", "consent_at"]
        export_order = fields

    def export_field(self, field, instance, **kwargs):
        # Visitors type these values; a leading = + - @ would run as a formula when opened in Excel.
        from ops.accounting import safe_cell

        return safe_cell(super().export_field(field, instance, **kwargs))


STATUS_COLORS = {"New": "info", "Contacted": "warning", "Quoted": "primary", "Won": "success", "Lost": "danger"}


@admin.register(LeadInquiry)
class LeadInquiryAdmin(ModelAdmin, ExportMixin):
    resource_classes = [LeadResource]
    export_form_class = ExportForm
    list_display = ["who", "buyer_type", "product", "quantity", "source", "status_badge", "status", "created_at", "whatsapp"]
    list_editable = ["status"]
    list_filter = ["status", "buyer_type", "source", "tier", ("created_at", RangeDateFilter)]
    list_filter_submit = True
    search_fields = ["name", "phone", "email", "business_name", "city", "message"]
    list_select_related = ["product"]
    autocomplete_fields = ["product"]
    raw_id_fields = ["variant", "package"]
    readonly_fields = ["created_at", "updated_at", "page_url"]
    date_hierarchy = "created_at"
    actions = ["mark_contacted", "mark_quoted", "mark_won", "mark_lost"]
    fieldsets = (
        ("Who", {"fields": ("name", "phone", "email", "business_name", "buyer_type", "city")}),
        ("What they want", {"fields": ("product", "variant", "package", "tier", "quantity", "message")}),
        ("Pipeline", {"fields": ("status", "notes", "source", "page_url", "created_at", "updated_at")}),
    )

    @display(description="Lead", header=True)
    def who(self, obj):
        return obj.name or obj.business_name or "Visitor", obj.phone or obj.email or "—"

    @display(description="Stage", label=STATUS_COLORS)
    def status_badge(self, obj):
        return obj.get_status_display()

    @display(description="")
    def whatsapp(self, obj):
        digits = "".join(ch for ch in obj.phone if ch.isdigit())
        if len(digits) == 10:
            digits = "91" + digits
        if not digits:
            return "—"
        return format_html('<a href="https://wa.me/{}" target="_blank" rel="noopener" style="color:#25D366;font-weight:600">Chat ↗</a>', digits)

    def _move(self, request, qs, status, label):
        messages.success(request, f"{qs.update(status=status)} lead(s) moved to '{label}'.")

    @admin.action(description="Move to: Contacted")
    def mark_contacted(self, request, qs):
        self._move(request, qs, LeadInquiry.Status.CONTACTED, "Contacted")

    @admin.action(description="Move to: Quoted")
    def mark_quoted(self, request, qs):
        self._move(request, qs, LeadInquiry.Status.QUOTED, "Quoted")

    @admin.action(description="Move to: Won 🎉")
    def mark_won(self, request, qs):
        self._move(request, qs, LeadInquiry.Status.WON, "Won")

    @admin.action(description="Move to: Lost")
    def mark_lost(self, request, qs):
        self._move(request, qs, LeadInquiry.Status.LOST, "Lost")
