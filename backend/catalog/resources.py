"""
Excel / CSV import & export definitions.

Owners can download a template, fill it in Excel or Google Sheets and upload
hundreds of products at once. Lists (badges, ingredients, benefits) are written
as comma-separated text so they are easy to type in a spreadsheet.
"""

from import_export import fields, resources, widgets

from .models import Badge, Category, Ingredient, PackageOption, Product, ProductVariant


class CategoryByNameWidget(widgets.ForeignKeyWidget):
    """Accepts a category NAME (creates it if new) instead of a database id."""

    def __init__(self):
        super().__init__(Category, field="name")

    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        obj, _ = Category.objects.get_or_create(name=str(value).strip())
        return obj


class NameListWidget(widgets.ManyToManyWidget):
    """'Vegan, SLS-free' → Badge objects (created automatically if new)."""

    def __init__(self, model):
        super().__init__(model, separator=",", field="name")

    def clean(self, value, row=None, **kwargs):
        if not value:
            return self.model.objects.none()
        names = [v.strip() for v in str(value).split(self.separator) if v.strip()]
        ids = [self.model.objects.get_or_create(name=n)[0].pk for n in names]
        return self.model.objects.filter(pk__in=ids)


class CommaListWidget(widgets.Widget):
    """JSON list ↔ 'a, b, c' text in a single spreadsheet cell."""

    def __init__(self, separator=","):
        self.separator = separator
        super().__init__()

    def clean(self, value, row=None, **kwargs):
        if not value:
            return []
        return [v.strip() for v in str(value).split(self.separator) if v.strip()]

    def render(self, value, obj=None, **kwargs):
        return f"{self.separator} ".join(value or [])


class ProductResource(resources.ModelResource):
    sku = fields.Field(attribute="sku", column_name="sku")
    category = fields.Field(attribute="category", column_name="category", widget=CategoryByNameWidget())
    badges = fields.Field(attribute="badges", column_name="badges", widget=NameListWidget(Badge))
    key_ingredients = fields.Field(attribute="key_ingredients", column_name="key_ingredients", widget=NameListWidget(Ingredient))
    key_benefits = fields.Field(attribute="key_benefits", column_name="key_benefits", widget=CommaListWidget("|"))
    suitable_for = fields.Field(attribute="suitable_for", column_name="suitable_for", widget=CommaListWidget())

    class Meta:
        model = Product
        import_id_fields = ["sku"]  # Re-uploading the same SKU updates the product instead of duplicating it.
        skip_unchanged = True
        report_skipped = True
        fields = [
            "sku", "title", "subtitle", "slug", "ean", "category", "description", "key_benefits", "how_to_use",
            "ingredients_text", "key_ingredients", "badges", "suitable_for", "mrp", "retail_price", "wholesale_price",
            "moq", "net_quantity", "unit", "shelf_life", "country_of_origin", "stock_status", "tags",
            "is_active", "is_featured", "is_new_arrival", "is_bestseller", "seo_title", "seo_description",
        ]
        export_order = fields


class ProductBySkuWidget(widgets.ForeignKeyWidget):
    def __init__(self):
        super().__init__(Product, field="sku")


class ProductVariantResource(resources.ModelResource):
    product = fields.Field(attribute="product", column_name="product_sku", widget=ProductBySkuWidget())

    class Meta:
        model = ProductVariant
        import_id_fields = ["product", "variant_type", "value"]
        fields = ["product", "variant_type", "value", "sku", "swatch_hex", "price_override", "stock_status", "order"]
        export_order = fields


class PackageOptionResource(resources.ModelResource):
    product = fields.Field(attribute="product", column_name="product_sku", widget=ProductBySkuWidget())

    class Meta:
        model = PackageOption
        import_id_fields = ["product", "name"]
        fields = ["product", "name", "units_per_pack", "retail_price", "wholesale_price", "moq", "order"]
        export_order = fields


TEMPLATE_EXAMPLE_ROWS = {
    "Products": [
        ["PAL-TB-001", "Bamboo Charcoal Toothbrush", "Ultra-soft charcoal bristles, compostable handle", "", "8901234567890",
         "Toothbrushes", "A calm, honest brush…", "Gentle on gums | Biodegradable handle", "Brush twice daily for 2 minutes.",
         "Handle: Moso bamboo. Bristles: charcoal-infused nylon.", "Activated Charcoal", "Vegan, BPA-free, Recyclable",
         "adults, sensitive", 149, 129, 72, 144, 1, "pcs", "Best before 36 months", "India", "in_stock",
         "bamboo, eco, charcoal", "TRUE", "TRUE", "FALSE", "TRUE", "", ""],
    ],
    "Variants": [["PAL-TB-001", "bristle", "Soft", "PAL-TB-001-S", "", "", "in_stock", 1]],
    "Packs": [["PAL-TB-001", "Pack of 3", 3, 349, 210, 20, 1], ["PAL-TB-001", "Carton of 144", 144, "", 9500, 1, 2]],
}
