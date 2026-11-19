"""
Catalog models: Category, Product (+ images, variants, pack sizes), Ingredient, Badge.

Built to grow from 15 to 50,000+ products: every field the website filters or sorts
on is indexed, and there is a fuzzy-search index on PostgreSQL.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import connection, models
from django.utils.text import slugify
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit

from storefront import validators as V
from storefront.utils import compress_image_field

hex_validator = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Please pick a colour (format like #8FC9B9).")


def unique_slug(instance, value, max_length=200):
    """Make a URL-friendly slug that no other row is using yet."""
    base = slugify(value)[: max_length - 6] or "item"
    slug, n = base, 2
    model = type(instance)
    while model.objects.filter(slug=slug).exclude(pk=instance.pk).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


class Category(models.Model):
    name = models.CharField(max_length=80, db_index=True, help_text="e.g. 'Toothbrushes'.")
    slug = models.SlugField(max_length=100, unique=True, blank=True, help_text="Web address part. Filled automatically.")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children",
                               help_text="Optional. Put 'Bamboo' under 'Toothbrushes' to make a sub-category.")
    description = models.TextField(blank=True, help_text="One or two lines shown on the category tile.")
    icon = models.CharField(max_length=40, blank=True, help_text="Optional icon name (e.g. 'sparkles', 'leaf', 'droplet').")
    image = models.ImageField(validators=V.IMAGE, upload_to="categories/", blank=True, help_text="Tile picture. Square works best.")
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True, help_text="Untick to hide this category and its products' tile.")

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return f"{self.parent} → {self.name}" if self.parent_id else self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, 100)
        compress_image_field(self.image, max_side=1200)
        super().save(*args, **kwargs)

    def descendant_ids(self):
        """This category plus every sub-category below it (any depth)."""
        ids, frontier = [self.pk], [self.pk]
        while frontier:
            frontier = list(Category.objects.filter(parent_id__in=frontier).values_list("pk", flat=True))
            ids += frontier
        return ids

    def get_absolute_url(self):
        return f"{settings.SITE_URL}/?category={self.slug}#catalog"


class Ingredient(models.Model):
    name = models.CharField(max_length=80, unique=True, help_text="e.g. 'Neem', 'Activated Charcoal'.")
    icon = models.CharField(max_length=40, blank=True, help_text="Optional icon name (e.g. 'leaf', 'sparkles', 'droplet').")
    image = models.ImageField(validators=V.IMAGE, upload_to="ingredients/", blank=True, help_text="Close-up picture for the Ingredient Spotlight.")
    short_benefit = models.CharField(max_length=120, blank=True, help_text="One short benefit, e.g. 'Naturally freshens breath'.")
    is_spotlight = models.BooleanField(default=False, help_text="Tick to feature it in the homepage Ingredient Spotlight.")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        compress_image_field(self.image, max_side=1400)
        super().save(*args, **kwargs)


class Badge(models.Model):
    name = models.CharField(max_length=40, unique=True, help_text="e.g. 'Fluoride-free'.")
    slug = models.SlugField(max_length=50, unique=True, blank=True, help_text="Used in filters, e.g. fluoride-free.")
    icon = models.CharField(max_length=40, blank=True, help_text="Optional icon name.")
    description = models.CharField(max_length=140, blank=True, help_text="What this badge means, in one line.")
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, 50)
        super().save(*args, **kwargs)


class ProductQuerySet(models.QuerySet):
    def live(self):
        return self.filter(is_active=True)

    def for_cards(self):
        """Everything a product card needs, in as few database queries as possible."""
        return self.select_related("category").prefetch_related(
            models.Prefetch("images", queryset=ProductImage.objects.order_by("order")),
            "badges",
            models.Prefetch("variants", queryset=ProductVariant.objects.order_by("order")),
            models.Prefetch("packages", queryset=PackageOption.objects.order_by("order")),
        )


class Product(models.Model):
    class StockStatus(models.TextChoices):
        IN_STOCK = "in_stock", "In stock"
        LOW = "low", "Low stock"
        MADE_TO_ORDER = "made_to_order", "Made to order"
        OUT = "out_of_stock", "Out of stock"

    class Unit(models.TextChoices):
        G = "g", "g (grams)"
        ML = "ml", "ml"
        PCS = "pcs", "pcs (pieces)"

    SUITABLE_CHOICES = [("adults", "Adults"), ("kids", "Kids"), ("sensitive", "Sensitive teeth"), ("braces", "Braces")]

    # --- Basics ---
    title = models.CharField(max_length=160, db_index=True, help_text="Product name as customers should see it.")
    subtitle = models.CharField(max_length=200, blank=True, help_text="One short line under the name, e.g. 'Ultra-soft bamboo brush with charcoal bristles'.")
    slug = models.SlugField(max_length=200, unique=True, blank=True, help_text="Web address part. Filled automatically from the name.")
    sku = models.CharField(max_length=60, unique=True, verbose_name="SKU", help_text="Your unique product code, e.g. PAL-TB-001.")
    ean = models.CharField(max_length=20, blank=True, db_index=True, verbose_name="EAN / barcode", help_text="Barcode number printed on the pack (optional).")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products", db_index=True,
                                 help_text="Where this product appears in the catalogue.")

    # --- Story & honest ingredients ---
    description = models.TextField(blank=True, help_text="Full description. Leave a blank line between paragraphs.")
    key_benefits = models.JSONField(default=list, blank=True, help_text='List of short benefits, e.g. ["Gentle on gums", "Biodegradable handle"].')
    how_to_use = models.TextField(blank=True, help_text="Simple steps. One step per line.")
    ingredients_text = models.TextField(blank=True, verbose_name="Full ingredients", help_text="Full ingredient list exactly as printed on the pack.")
    key_ingredients = models.ManyToManyField(Ingredient, blank=True, related_name="products", help_text="Hero ingredients shown as icon chips.")
    badges = models.ManyToManyField(Badge, blank=True, related_name="products", help_text="Free-from, vegan, dentist-recommended…")
    suitable_for = models.JSONField(default=list, blank=True,
                                    help_text="Who it's for. Any of: adults, kids, sensitive, braces.")
    demo_video = models.FileField(validators=V.VIDEO, upload_to="products/videos/", blank=True, help_text="Optional short MP4 showing the product (under 8 MB).")

    # --- Prices (₹, incl. all taxes) ---
    mrp = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="MRP ₹",
                              help_text="Price printed on the pack, including all taxes, in ₹.")
    retail_price = models.DecimalField(max_digits=10, decimal_places=2, db_index=True, verbose_name="Retail price ₹",
                                       help_text="What a shopper pays for one piece, in ₹ (incl. taxes).")
    wholesale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Wholesale price ₹",
                                          help_text="Per-piece price for businesses buying in bulk, in ₹. Leave empty to hide wholesale.")
    moq = models.PositiveIntegerField(default=1, verbose_name="Minimum order (MOQ)", help_text="Smallest number of pieces a business can order at wholesale price.")
    discount_percent = models.PositiveSmallIntegerField(default=0, db_index=True, validators=[MaxValueValidator(90)],
                                                        help_text="Calculated automatically from MRP and retail price. You can also use the 'Apply discount' bulk action.")

    # --- Pack facts ---
    net_quantity = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Amount in the pack, e.g. 100.")
    unit = models.CharField(max_length=4, choices=Unit.choices, default=Unit.PCS)
    shelf_life = models.CharField(max_length=80, blank=True, help_text="e.g. 'Best before 24 months from manufacture'.")
    country_of_origin = models.CharField(max_length=60, default="India")
    stock_status = models.CharField(max_length=16, choices=StockStatus.choices, default=StockStatus.IN_STOCK, db_index=True,
                                    help_text="Updated automatically from the Inventory Manager once stock is tracked.")
    tags =models.CharField(max_length=300, blank=True, help_text="Extra search words, comma separated, e.g. 'charcoal, travel, eco'.")

    # --- Visibility ---
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Show on website")
    is_featured = models.BooleanField(default=False, db_index=True, verbose_name="Featured")
    is_new_arrival = models.BooleanField(default=False, db_index=True, verbose_name="New arrival")
    is_bestseller = models.BooleanField(default=False, db_index=True, verbose_name="Bestseller")
    order = models.PositiveIntegerField(default=0, db_index=True, help_text="Lower numbers show first in 'Featured' lists.")

    # --- 3D model ---
    model_3d = models.FileField(upload_to="products/3d/", blank=True, validators=V.MODEL_3D, verbose_name="3D model (.glb)",
                                help_text="Optional .glb 3D model (binary glTF). Keep it under 5 MB for fast phones; 20 MB maximum.")
    model_poster = models.ImageField(upload_to="products/3d/", blank=True, validators=V.IMAGE, verbose_name="3D poster image",
                                     help_text="Picture shown instantly while the 3D model loads (same angle as the model). "
                                               "Empty = the first product photo.")
    is_hero_3d_featured = models.BooleanField(default=False, db_index=True, verbose_name="Show in the 3D hero",
                                              help_text="Feature this product's 3D model in the homepage '3D showcase' hero.")
    hero_3d_order = models.PositiveIntegerField(default=0, verbose_name="3D hero order", help_text="Lower numbers show first.")

    # --- SEO ---
    seo_title =models.CharField(max_length=70, blank=True, help_text="Optional. Title for Google (under 60 characters).")
    seo_description = models.CharField(max_length=170, blank=True, help_text="Optional. Description for Google (under 160 characters).")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "category", "-created_at"], name="product_active_cat_new"),
            models.Index(fields=["is_active", "-is_bestseller", "-created_at"], name="product_active_best"),
            models.Index(fields=["is_active", "retail_price"], name="product_active_price"),
            # Fuzzy-search (pg_trgm GIN) indexes are created in migration 0002 on PostgreSQL only.
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.title)
        compress_image_field(self.model_poster, max_side=1600)
        if self.mrp and self.retail_price and self.mrp > 0 and self.retail_price < self.mrp:
            pct = (Decimal(1) - self.retail_price / self.mrp) * 100
            self.discount_percent = int(pct.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        elif self.mrp and self.retail_price is not None and self.retail_price >= self.mrp:
            self.discount_percent = 0
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.retail_price and self.mrp and self.retail_price > self.mrp:
            errors["retail_price"] = "The retail price can't be higher than the MRP printed on the pack."
        if self.wholesale_price and self.retail_price and self.wholesale_price > self.retail_price:
            errors["wholesale_price"] = "The wholesale price is usually lower than the retail price — please check."
        bad = [s for s in (self.suitable_for or []) if s not in dict(self.SUITABLE_CHOICES)]
        if bad:
            errors["suitable_for"] = f"Unknown value(s): {', '.join(bad)}. Use adults, kids, sensitive or braces."
        if errors:
            raise ValidationError(errors)

    def get_absolute_url(self):
        return f"{settings.SITE_URL}/p/{self.slug}"


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(validators=V.IMAGE, upload_to="products/", help_text="Large phone photos are fine — we resize & convert to WebP automatically.")
    alt_text = models.CharField(max_length=160, blank=True, help_text="Describe the picture for blind visitors & Google.")
    order = models.PositiveIntegerField(default=0, db_index=True)

    # Auto-generated smaller copies for fast loading.
    thumb = ImageSpecField(source="image", processors=[ResizeToFit(480, 600)], format="WEBP", options={"quality": 78})
    medium = ImageSpecField(source="image", processors=[ResizeToFit(960, 1200)], format="WEBP", options={"quality": 80})

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"Image {self.order} of {self.product}"

    def save(self, *args, **kwargs):
        compress_image_field(self.image, max_side=2000)
        super().save(*args, **kwargs)


class ProductVariant(models.Model):
    class VariantType(models.TextChoices):
        BRISTLE = "bristle", "Bristle"
        FLAVOUR = "flavour", "Flavour"
        SIZE = "size", "Size"
        COLOUR = "colour", "Colour"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    variant_type = models.CharField(max_length=10, choices=VariantType.choices, db_index=True)
    value = models.CharField(max_length=60, db_index=True, help_text="e.g. 'Soft', 'Mint', '100 g', 'Ocean Blue'.")
    sku = models.CharField(max_length=60, blank=True, verbose_name="SKU", help_text="Optional code for this variant.")
    swatch_hex = models.CharField(max_length=7, blank=True, validators=[hex_validator], help_text="Optional colour dot for colour variants.")
    image = models.ImageField(validators=V.IMAGE, upload_to="products/variants/", blank=True, help_text="Optional picture shown when this variant is selected.")
    price_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                         help_text="Only if this variant costs differently (retail, ₹).")
    stock_status = models.CharField(max_length=16, choices=Product.StockStatus.choices, default=Product.StockStatus.IN_STOCK)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        indexes = [models.Index(fields=["variant_type", "value"], name="variant_type_value")]

    def __str__(self):
        return f"{self.get_variant_type_display()}: {self.value}"

    def save(self, *args, **kwargs):
        compress_image_field(self.image, max_side=2000)
        super().save(*args, **kwargs)


class PackageOption(models.Model):
    PRESET_NAMES = ["Single", "Pack of 3", "Pack of 6", "Box of 12", "Box of 24", "Carton of 144",
                    "Hotel Amenity Kit", "Custom / Private Label"]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="packages")
    name = models.CharField(max_length=60, help_text="e.g. 'Pack of 3', 'Carton of 144', 'Hotel Amenity Kit'.")
    units_per_pack = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], help_text="How many pieces inside.")
    retail_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                       help_text="Retail price for the whole pack, ₹. Empty = pieces × product retail price.")
    wholesale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                          help_text="Wholesale price for the whole pack, ₹. Empty = pieces × product wholesale price.")
    moq = models.PositiveIntegerField(null=True, blank=True, verbose_name="MOQ (packs)", help_text="Minimum packs for wholesale. Empty = use product MOQ.")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.name} ({self.units_per_pack} pcs)"


def is_postgres():
    return connection.vendor == "postgresql"
