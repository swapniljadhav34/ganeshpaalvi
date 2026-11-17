"""
Product admin — the screen the owner will use most.

  • Drag-to-reorder photo uploads with live previews (auto WebP on save)
  • Variants and pack sizes edited right inside the product
  • Bulk actions: show/hide, featured, discount %, change category, stock status
  • Excel/CSV import & export, plus a downloadable template
"""

from decimal import ROUND_HALF_UP, Decimal

from django import forms
from django.contrib import admin, messages
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from unfold.contrib.filters.admin import RangeNumericFilter
from unfold.contrib.import_export.forms import ExportForm, ImportForm
from unfold.decorators import action, display
from unfold.widgets import UnfoldAdminColorInputWidget, UnfoldAdminSelectWidget

from storefront.admin import view_on_site_link

from .models import Badge, Category, Ingredient, PackageOption, Product, ProductImage, ProductVariant
from .resources import (
    TEMPLATE_EXAMPLE_ROWS,
    PackageOptionResource,
    ProductResource,
    ProductVariantResource,
)


# --- Small reusable bits ----------------------------------------------------
def image_tag(url, size=56):
    return format_html(
        '<img src="{}" loading="lazy" style="width:{}px;height:{}px;object-fit:cover;border-radius:10px;background:#f3f2ee">',
        url, size, int(size * 1.25),
    )


class ImageWithPreviewWidget(forms.ClearableFileInput):
    """File picker that shows the current picture AND a live preview of a new pick."""

    def render(self, name, value, attrs=None, renderer=None):
        html = super().render(name, value, attrs, renderer)
        current = getattr(value, "url", "") if value else ""
        pid = (attrs or {}).get("id", name)
        return format_html(
            '<div style="display:flex;gap:14px;align-items:center">'
            '<img id="{}-preview" src="{}" style="width:72px;height:90px;object-fit:cover;border-radius:12px;'
            'background:#f3f2ee;{}"><div>{}</div></div>'
            "<script>(function(){{const i=document.getElementById('{}');if(!i)return;i.addEventListener('change',e=>{{"
            "const f=e.target.files[0];if(!f)return;const p=document.getElementById('{}-preview');"
            "p.src=URL.createObjectURL(f);p.style.display='block';}});}})();</script>",
            pid, current, "" if current else "display:none", html, pid, pid,
        )


# --- Inlines ----------------------------------------------------------------
class ProductImageInline(TabularInline):
    model = ProductImage
    extra = 1
    fields = ["image", "alt_text"]
    ordering_field = "order"
    hide_ordering_field = True
    formfield_overrides = {}

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "image":
            kwargs["widget"] = ImageWithPreviewWidget
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class ProductVariantInline(TabularInline):
    model = ProductVariant
    extra = 0
    fields = ["variant_type", "value", "swatch_hex", "image", "price_override", "stock_status", "sku"]
    ordering_field = "order"
    hide_ordering_field = True
    tab = True

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "swatch_hex":
            kwargs["widget"] = UnfoldAdminColorInputWidget
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class PackageOptionForm(forms.ModelForm):
    name = forms.CharField(
        help_text="Pick or type a name: " + ", ".join(PackageOption.PRESET_NAMES),
        widget=forms.TextInput(attrs={"list": "paalvi-pack-names"}),
    )

    class Meta:
        model = PackageOption
        fields = "__all__"


class PackageOptionInline(TabularInline):
    model = PackageOption
    form = PackageOptionForm
    extra = 0
    fields = ["name", "units_per_pack", "retail_price", "wholesale_price", "moq"]
    ordering_field = "order"
    hide_ordering_field = True
    tab = True


# --- Product form (friendly multi-choice for "suitable for") ----------------
class ProductForm(forms.ModelForm):
    suitable_for = forms.MultipleChoiceField(
        choices=Product.SUITABLE_CHOICES, required=False, widget=forms.CheckboxSelectMultiple,
        help_text="Who is this product for?",
    )
    key_benefits = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 4}),
        help_text="One benefit per line, e.g. 'Gentle on gums'.",
    )

    class Meta:
        model = Product
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial["key_benefits"] = "\n".join(self.instance.key_benefits or [])

    def clean_key_benefits(self):
        raw = self.cleaned_data.get("key_benefits") or ""
        return [line.strip(" •-\t") for line in raw.splitlines() if line.strip(" •-\t")]


class BulkDiscountForm(forms.Form):
    discount_percent = forms.IntegerField(min_value=0, max_value=90, label="Discount % off MRP",
                                          help_text="We set the retail price to MRP minus this %. Use 0 to remove discounts.")


class BulkCategoryForm(forms.Form):
    category = forms.ModelChoiceField(queryset=Category.objects.all(), widget=UnfoldAdminSelectWidget)


# --- Product admin ----------------------------------------------------------
@admin.register(Product)
class ProductAdmin(ModelAdmin, ImportExportModelAdmin):
    form = ProductForm
    resource_classes = [ProductResource]
    import_form_class = ImportForm
    export_form_class = ExportForm
    inlines = [ProductImageInline, ProductVariantInline, PackageOptionInline]
    list_display = ["cover", "title_block", "category", "price_block", "stock_badge", "flags", "is_active", "site_link"]
    list_display_links = ["cover", "title_block"]
    list_editable = ["is_active"]
    list_filter = [
        "is_active", "stock_status", "category", "is_featured", "is_bestseller", "is_new_arrival", "badges",
        ("retail_price", RangeNumericFilter),
    ]
    list_filter_submit = True
    search_fields = ["title", "sku", "ean", "tags"]
    autocomplete_fields = ["category", "key_ingredients", "badges"]
    readonly_fields = ["discount_percent", "created_at", "updated_at", "site_link"]
    list_per_page = 50
    show_full_result_count = False  # keeps the list fast with 50,000+ products
    save_on_top = True
    warn_unsaved_form = True
    change_form_after_template = "admin/catalog/pack_names_datalist.html"
    actions = ["activate", "deactivate", "mark_featured", "unmark_featured", "mark_low_stock", "mark_in_stock",
               "mark_out_of_stock", "apply_discount", "change_category"]
    actions_list = ["download_template"]
    fieldsets = (
        ("Basics", {"fields": ("title", "subtitle", "category", ("sku", "ean"), "slug", "site_link")}),
        ("Prices (₹, incl. all taxes)", {"fields": (("mrp", "retail_price", "discount_percent"), ("wholesale_price", "moq"))}),
        ("Story", {"fields": ("description", "key_benefits", "how_to_use", "demo_video")}),
        ("Honest ingredients", {"fields": ("key_ingredients", "ingredients_text", "badges", "suitable_for")}),
        ("Pack details", {"fields": (("net_quantity", "unit"), "shelf_life", "country_of_origin", "stock_status", "tags")}),
        ("Show on website", {"fields": (("is_active", "is_featured"), ("is_new_arrival", "is_bestseller"), "order")}),
        ("Google (optional)", {"fields": ("seo_title", "seo_description"), "classes": ["collapse"]}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("category").prefetch_related("images")

    # ---- list columns ----
    @display(description="")
    def cover(self, obj):
        first = next(iter(obj.images.all()), None)
        return image_tag(first.thumb.url) if first else image_tag("", 56)

    @display(description="Product", header=True)
    def title_block(self, obj):
        return obj.title, obj.sku

    @display(description="Price")
    def price_block(self, obj):
        rp = f"₹{obj.retail_price:,.0f}"
        mrp = f"₹{obj.mrp:,.0f}" if obj.mrp and obj.mrp > obj.retail_price else ""
        ws = f"Wholesale ₹{obj.wholesale_price:,.0f} · MOQ {obj.moq}" if obj.wholesale_price else "Retail only"
        return format_html("<strong>{}</strong> <s style='opacity:.5'>{}</s><br><span style='opacity:.65;font-size:12px'>{}</span>",
                           rp, mrp, ws)

    @display(description="Stock", label={
        "In stock": "success", "Low stock": "warning", "Made to order": "info", "Out of stock": "danger"})
    def stock_badge(self, obj):
        return obj.get_stock_status_display()

    @display(description="Tags")
    def flags(self, obj):
        bits = [("★ Featured", obj.is_featured), ("Bestseller", obj.is_bestseller), ("New", obj.is_new_arrival)]
        return format_html(" ".join(
            f"<span style='font-size:11px;padding:2px 8px;border-radius:99px;background:#eef8f5;color:#315f55'>{t}</span>"
            for t, on in bits if on) or "—")

    @display(description="")
    def site_link(self, obj):
        return view_on_site_link(obj.get_absolute_url()) if obj.pk else "Save first to preview"

    # ---- bulk actions ----
    @admin.action(description="Show on website")
    def activate(self, request, qs):
        messages.success(request, f"{qs.update(is_active=True)} product(s) are now visible.")

    @admin.action(description="Hide from website")
    def deactivate(self, request, qs):
        messages.success(request, f"{qs.update(is_active=False)} product(s) hidden.")

    @admin.action(description="Mark as featured")
    def mark_featured(self, request, qs):
        messages.success(request, f"{qs.update(is_featured=True)} product(s) featured.")

    @admin.action(description="Remove from featured")
    def unmark_featured(self, request, qs):
        messages.success(request, f"{qs.update(is_featured=False)} product(s) un-featured.")

    @admin.action(description="Mark as low stock")
    def mark_low_stock(self, request, qs):
        messages.success(request, f"{qs.update(stock_status=Product.StockStatus.LOW)} product(s) marked low stock.")

    @admin.action(description="Mark as in stock")
    def mark_in_stock(self, request, qs):
        messages.success(request, f"{qs.update(stock_status=Product.StockStatus.IN_STOCK)} product(s) marked in stock.")

    @admin.action(description="Mark as out of stock")
    def mark_out_of_stock(self, request, qs):
        messages.success(request, f"{qs.update(stock_status=Product.StockStatus.OUT)} product(s) marked out of stock.")

    @admin.action(description="Apply discount %% (sets retail price from MRP)")
    def apply_discount(self, request, qs):
        if "apply" in request.POST:
            form = BulkDiscountForm(request.POST)
            if form.is_valid():
                pct = Decimal(form.cleaned_data["discount_percent"])
                n = 0
                for p in qs:
                    p.retail_price = (p.mrp * (Decimal(100) - pct) / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    p.save()  # recalculates discount_percent & clears caches
                    n += 1
                messages.success(request, f"{pct}% off applied to {n} product(s).")
                return None
        else:
            form = BulkDiscountForm()
        return render(request, "admin/catalog/bulk_form.html", {
            **self.admin_site.each_context(request), "title": "Apply a discount", "form": form, "queryset": qs,
            "action": "apply_discount", "opts": self.model._meta,
        })

    @admin.action(description="Move to another category")
    def change_category(self, request, qs):
        if "apply" in request.POST:
            form = BulkCategoryForm(request.POST)
            if form.is_valid():
                n = qs.update(category=form.cleaned_data["category"])
                messages.success(request, f"{n} product(s) moved to {form.cleaned_data['category']}.")
                return None
        else:
            form = BulkCategoryForm()
        return render(request, "admin/catalog/bulk_form.html", {
            **self.admin_site.each_context(request), "title": "Move products to a category", "form": form,
            "queryset": qs, "action": "change_category", "opts": self.model._meta,
        })

    # ---- downloadable Excel template ----
    @action(description="Download Excel template", url_path="download-template", icon="download")
    def download_template(self, request):
        wb = Workbook()
        guide = wb.active
        guide.title = "How to use"
        for line in [
            "PAALVI — product upload template",
            "",
            "1. Fill the 'Products' sheet: one row per product. 'sku' must be unique — re-uploading the same SKU updates it.",
            "2. 'category', 'badges' and 'key_ingredients' use names; new names are created automatically.",
            "3. Separate badges/ingredients/suitable_for with commas. Separate key_benefits with |",
            "4. suitable_for accepts: adults, kids, sensitive, braces. stock_status: in_stock, low, made_to_order, out_of_stock.",
            "5. Prices are in ₹ including all taxes. Leave wholesale_price empty for retail-only products.",
            "6. Save each sheet as its own file (or CSV) and upload: Products → Import, then Variants and Pack sizes → Import.",
            "7. Photos: add them in the product page after importing (drag to reorder).",
        ]:
            guide.append([line])
        guide["A1"].font = Font(bold=True, size=14)
        guide.column_dimensions["A"].width = 120
        header_fill = PatternFill("solid", fgColor="D7EFE8")
        for title, resource in [("Products", ProductResource), ("Variants", ProductVariantResource), ("Packs", PackageOptionResource)]:
            ws = wb.create_sheet(title)
            headers = [f.column_name for f in resource().get_export_fields()]
            ws.append(headers)
            for cell in ws[1]:
                cell.font, cell.fill = Font(bold=True), header_fill
            for row in TEMPLATE_EXAMPLE_ROWS[title]:
                ws.append(row)
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = 18
        resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = 'attachment; filename="paalvi-product-template.xlsx"'
        wb.save(resp)
        return resp


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ["name", "parent", "product_count", "is_active", "site_link"]
    list_editable = ["is_active"]
    list_filter = ["is_active", "parent"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}
    ordering_field = "order"
    hide_ordering_field = True
    autocomplete_fields = ["parent"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("parent").annotate(n=Count("products"))

    @display(description="Products", ordering="n")
    def product_count(self, obj):
        return obj.n

    @display(description="")
    def site_link(self, obj):
        return view_on_site_link(obj.get_absolute_url())


@admin.register(Ingredient)
class IngredientAdmin(ModelAdmin):
    list_display = ["name", "short_benefit", "is_spotlight"]
    list_editable = ["is_spotlight"]
    search_fields = ["name"]


@admin.register(Badge)
class BadgeAdmin(ModelAdmin):
    list_display = ["name", "slug", "description"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}
    ordering_field = "order"
    hide_ordering_field = True


@admin.register(ProductVariant)
class ProductVariantAdmin(ModelAdmin, ImportExportModelAdmin):
    resource_classes = [ProductVariantResource]
    import_form_class = ImportForm
    export_form_class = ExportForm
    list_display = ["product", "variant_type", "value", "price_override", "stock_status"]
    list_filter = ["variant_type", "stock_status"]
    search_fields = ["product__title", "product__sku", "value"]
    autocomplete_fields = ["product"]
    list_select_related = ["product"]


@admin.register(PackageOption)
class PackageOptionAdmin(ModelAdmin, ImportExportModelAdmin):
    resource_classes = [PackageOptionResource]
    import_form_class = ImportForm
    export_form_class = ExportForm
    list_display = ["product", "name", "units_per_pack", "retail_price", "wholesale_price", "moq"]
    search_fields = ["product__title", "product__sku", "name"]
    autocomplete_fields = ["product"]
    list_select_related = ["product"]
