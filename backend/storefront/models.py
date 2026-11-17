"""
Storefront models: everything about how the website LOOKS and SPEAKS.

  Brand & Contact      → BrandSettings (one row)
  Theme & Festivals    → ThemePreset, ActiveTheme (one row), FestivalSchedule
  Homepage Builder     → HeroSlide, PageSection
  AI Concierge         → AIAssistantConfig (one row)
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

from . import design as D
from .utils import SingletonModel, compress_image_field, contrast_ratio

hex_validator = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Please pick a colour (format like #8FC9B9).")
whatsapp_validator = RegexValidator(
    r"^\+?\d{10,15}$",
    "Enter the WhatsApp number with country code and no spaces, e.g. +919876543210.",
)


class ScheduleMixin(models.Model):
    """Optional 'show from / until' dates. Leave empty to show always."""

    show_from = models.DateTimeField(null=True, blank=True, help_text="Optional. Start showing this from this date & time.")
    show_until = models.DateTimeField(null=True, blank=True, help_text="Optional. Stop showing this after this date & time.")

    class Meta:
        abstract = True

    @classmethod
    def live_q(cls):
        """Database filter for 'active and inside its schedule right now'."""
        now = timezone.now()
        return (
            models.Q(is_active=True)
            & (models.Q(show_from__isnull=True) | models.Q(show_from__lte=now))
            & (models.Q(show_until__isnull=True) | models.Q(show_until__gte=now))
        )


class DesignFields(models.Model):
    """Shape & animation controls shared by hero slides and page sections.
    Leave any of them on 'Use site default' to follow the Site Design Studio."""

    media_shape = models.CharField(max_length=20, blank=True, choices=D.choices(D.SHAPES, True),
                                   help_text="Shape of the photos / videos in this block.")
    entrance_animation = models.CharField(max_length=20, blank=True, choices=D.choices(D.ENTRANCES, True),
                                          help_text="How this block appears when it scrolls into view.")
    text_animation = models.CharField(max_length=20, blank=True, choices=D.choices(D.TEXT_ANIMATIONS, True),
                                      help_text="How the headline animates in.")
    hover_effect = models.CharField(max_length=20, blank=True, choices=D.choices(D.HOVER_EFFECTS, True),
                                    help_text="What photos and cards do when the mouse moves over them.")
    media_motion = models.CharField(max_length=20, blank=True, choices=D.choices(D.MEDIA_MOTIONS, True),
                                    help_text="Gentle movement the media keeps doing on its own.")
    gallery_style = models.CharField(max_length=20, blank=True, choices=D.choices(D.GALLERY_STYLES, True),
                                     help_text="When you add several photos/videos: how they rotate.")
    gallery_interval = models.PositiveSmallIntegerField(default=5, validators=[MinValueValidator(2), MaxValueValidator(30)],
                                                        help_text="Seconds each photo stays before the next one (2–30).")
    pointer_effect = models.CharField(max_length=20, blank=True, choices=D.choices(D.POINTER_EFFECTS, True),
                                      help_text="How the whole block reacts to the mouse (or touch).")
    decor_shape = models.CharField(max_length=20, blank=True, choices=D.choices(D.DECOR_SHAPES, True),
                                   help_text="Decorative animated shape drawn in the background.")
    divider_shape = models.CharField(max_length=20, blank=True, choices=D.choices(D.DIVIDERS, True),
                                     help_text="Shape of the edge where this block meets the previous one.")
    animation_speed = models.CharField(max_length=10, blank=True, choices=D.choices(D.SPEEDS, True))

    DESIGN_FIELDS = ["media_shape", "entrance_animation", "text_animation", "hover_effect", "media_motion",
                     "gallery_style", "gallery_interval", "pointer_effect", "decor_shape", "divider_shape", "animation_speed"]

    class Meta:
        abstract = True

    def design_payload(self):
        return {f: getattr(self, f) for f in self.DESIGN_FIELDS}


class MediaItemBase(models.Model):
    """One photo or video in a gallery. Add several and they rotate automatically."""

    image = models.ImageField(upload_to="gallery/", blank=True, help_text="Photo (JPG/PNG/WebP — converted to WebP automatically).")
    video = models.FileField(upload_to="gallery/", blank=True, help_text="Or a short MP4/WebM video (under 8 MB, no sound). "
                                                                       "The photo above is used as its cover.")
    caption = models.CharField(max_length=120, blank=True, help_text="Optional small caption shown on the photo.")
    link = models.CharField(max_length=300, blank=True, help_text="Optional link when tapped, e.g. /p/bamboo-brush.")
    alt_text = models.CharField(max_length=140, blank=True, help_text="Describe the picture for blind visitors and Google.")
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ["order"]

    def __str__(self):
        return self.caption or self.alt_text or f"Media #{self.pk}"

    def save(self, *args, **kwargs):
        compress_image_field(self.image, max_side=2000)
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# 1. Brand & Contact
# ---------------------------------------------------------------------------
class BrandSettings(SingletonModel):
    brand_name = models.CharField(max_length=60, default="Paalvi", help_text="Your brand name as shown on the website.")
    tagline = models.CharField(max_length=140, default="Everyday essentials, elevated.", blank=True,
                               help_text="A short line that sums up your brand.")
    logo_light = models.FileField(upload_to="brand/", blank=True,
                                  help_text="Logo for dark backgrounds (usually white). PNG, WebP or SVG.")
    logo_dark = models.FileField(upload_to="brand/", blank=True,
                                 help_text="Logo for light backgrounds (usually dark). PNG, WebP or SVG.")
    favicon = models.FileField(upload_to="brand/", blank=True, help_text="Tiny square icon shown in the browser tab (512×512 PNG is ideal).")

    contact_email = models.EmailField(blank=True, default="hello@paalvi.in", help_text="Where customers can email you.")
    whatsapp_number = models.CharField(max_length=16, default="+91", validators=[whatsapp_validator],
                                       help_text="WhatsApp number with country code, e.g. +919876543210. All 'WhatsApp' buttons use this.")
    phone = models.CharField(max_length=20, blank=True, help_text="Phone number shown on the site (optional).")
    instagram_url = models.URLField(blank=True, help_text="Full link to your Instagram page.")
    facebook_url = models.URLField(blank=True, help_text="Full link to your Facebook page.")
    x_url = models.URLField(blank=True, verbose_name="X (Twitter) URL", help_text="Full link to your X (Twitter) profile.")

    registered_address = models.TextField(blank=True, help_text="Your registered business address (shown in the footer).")
    google_maps_link = models.URLField(blank=True, help_text="Paste a Google Maps share link to your location.")
    gstin = models.CharField(max_length=15, blank=True, verbose_name="GSTIN", help_text="Your 15-character GST number (optional).")
    manufacturer_details = models.TextField(blank=True, help_text="Manufactured by — name & address, as printed on the pack.")
    marketer_details = models.TextField(blank=True, help_text="Marketed by — name & address, as printed on the pack.")
    customer_care_details = models.TextField(blank=True, help_text="Customer care contact, as printed on the pack.")

    announcement_text = models.CharField(max_length=160, blank=True, help_text="Short message in the thin bar at the very top of the site.")
    announcement_link = models.CharField(max_length=300, blank=True, help_text="Optional link when the bar is tapped (e.g. /p/bamboo-brush or a full URL).")
    announcement_active = models.BooleanField(default=False, help_text="Tick to show the announcement bar.")
    announcement_more = models.TextField(blank=True, help_text="Optional extra messages, one per line. They rotate or scroll "
                                                               "with the first one (choose the style in Site Design Studio).")

    footer_story = models.TextField(blank=True, help_text="A few warm lines about Paalvi shown in the footer.")
    default_seo_title = models.CharField(max_length=70, default="Paalvi — Everyday essentials, elevated", help_text="Title shown in Google results (keep under 60 characters).")
    default_seo_description = models.CharField(max_length=170, blank=True,
                                               default="Premium toothbrushes, toothpaste and oral care made for India. Retail and wholesale.",
                                               help_text="Description shown in Google results (keep under 160 characters).")
    og_share_image = models.ImageField(upload_to="brand/", blank=True,
                                       help_text="Picture shown when someone shares your site on WhatsApp/Facebook (1200×630 is ideal).")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Brand & contact details"
        verbose_name_plural = "Brand & contact details"

    def __str__(self):
        return f"{self.brand_name} — brand & contact"

    def save(self, *args, **kwargs):
        compress_image_field(self.og_share_image, max_side=1600)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"{settings.SITE_URL}/"


# ---------------------------------------------------------------------------
# 2. Theme & Festival Studio
# ---------------------------------------------------------------------------
class ThemePreset(models.Model):
    class Kind(models.TextChoices):
        EVERYDAY = "everyday", "Everyday"
        FESTIVAL = "festival", "Festival"

    class DisplayFont(models.TextChoices):
        INSTRUMENT = "instrument", "Instrument Serif (calm, editorial)"
        FRAUNCES = "fraunces", "Fraunces (warm, rounded)"
        TIRO = "tiro", "Tiro Devanagari (festive, Indian)"

    class Ambient(models.TextChoices):
        NONE = "none", "None (calm)"
        BUBBLES = "bubbles", "Bubbles"
        MIST = "mist", "Mist / Steam"
        RIPPLE = "ripple", "Water Ripple"
        DIYAS = "diyas", "Diyas / Sparks"
        GULAL = "gulal", "Gulal / Confetti"
        SNOW = "snow", "Snowfall"
        PETALS = "petals", "Petals"

    name = models.CharField(max_length=60, unique=True, help_text="A friendly name, e.g. 'Diwali Royal Gold'.")
    slug = models.SlugField(max_length=60, unique=True, help_text="Short code used internally. Filled automatically.")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.EVERYDAY)
    description = models.CharField(max_length=160, blank=True, help_text="When to use this look.")

    primary = models.CharField(max_length=7, validators=[hex_validator], default="#8FC9B9", help_text="Main brand colour — buttons, highlights.")
    secondary = models.CharField(max_length=7, validators=[hex_validator], default="#E6CFC3", help_text="Supporting colour — soft backgrounds, chips.")
    accent = models.CharField(max_length=7, validators=[hex_validator], default="#BFA77A", help_text="Used sparingly for premium touches.")
    surface = models.CharField(max_length=7, validators=[hex_validator], default="#F8F7F4", help_text="Page background colour.")
    surface_elevated = models.CharField(max_length=7, validators=[hex_validator], default="#FFFFFF", help_text="Card & panel background colour.")
    text = models.CharField(max_length=7, validators=[hex_validator], default="#14181F", help_text="Main text colour.")
    text_muted = models.CharField(max_length=7, validators=[hex_validator], default="#5B6470", help_text="Softer text colour for captions.")

    display_font = models.CharField(max_length=12, choices=DisplayFont.choices, default=DisplayFont.INSTRUMENT,
                                    help_text="Font used for big headlines.")
    ambient_effect = models.CharField(max_length=10, choices=Ambient.choices, default=Ambient.NONE,
                                      help_text="Gentle background animation. Turned off automatically on slow phones.")
    preview_image = models.ImageField(upload_to="themes/", blank=True, help_text="Optional picture to recognise this theme.")
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Theme preset"

    def __str__(self):
        return self.name

    @property
    def text_contrast(self):
        return contrast_ratio(self.text, self.surface)

    @property
    def muted_contrast(self):
        return contrast_ratio(self.text_muted, self.surface)

    def contrast_warnings(self):
        """Plain-English warnings when text would be hard to read (WCAG AA)."""
        warnings = []
        if self.text_contrast < 4.5:
            warnings.append(f"Main text on the background is hard to read (contrast {self.text_contrast}:1, needs 4.5:1).")
        if self.muted_contrast < 4.5:
            warnings.append(f"Soft caption text on the background is hard to read (contrast {self.muted_contrast}:1, needs 4.5:1).")
        if contrast_ratio(self.text, self.surface_elevated) < 4.5:
            warnings.append("Main text on cards is hard to read — try a darker text or lighter card colour.")
        return warnings

    def as_tokens(self):
        return {
            "slug": self.slug,
            "name": self.name,
            "kind": self.kind,
            "primary": self.primary,
            "secondary": self.secondary,
            "accent": self.accent,
            "surface": self.surface,
            "surface_elevated": self.surface_elevated,
            "text": self.text,
            "text_muted": self.text_muted,
            "display_font": self.display_font,
            "ambient_effect": self.ambient_effect,
        }

    def save(self, *args, **kwargs):
        from django.utils.text import slugify

        if not self.slug:
            self.slug = slugify(self.name)[:60]
        compress_image_field(self.preview_image, max_side=1200)
        super().save(*args, **kwargs)


class ActiveTheme(SingletonModel):
    default_preset = models.ForeignKey(ThemePreset, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
                                       help_text="Your everyday look, used when no festival is running.")
    manual_override = models.ForeignKey(ThemePreset, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
                                        help_text="Force this theme right now, ignoring all festival dates. Leave empty to let the schedule decide.")
    enable_ambient_effects = models.BooleanField(default=True, help_text="Untick to switch off all background animations site-wide.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Active theme & festival schedule"
        verbose_name_plural = "Active theme & festival schedule"

    def __str__(self):
        return "Active theme"

    def resolve(self, now=None):
        """Which preset should the site wear right now? Override > festival > default."""
        if self.manual_override_id:
            return self.manual_override, "manual"
        today = (now or timezone.localtime()).date()
        fest = (
            self.festivals.filter(is_active=True, start_date__lte=today, end_date__gte=today)
            .select_related("preset")
            .order_by("start_date")
            .first()
        )
        if fest:
            return fest.preset, "festival"
        if self.default_preset_id:
            return self.default_preset, "default"
        return ThemePreset.objects.order_by("order").first(), "fallback"


class FestivalSchedule(models.Model):
    active_theme = models.ForeignKey(ActiveTheme, on_delete=models.CASCADE, related_name="festivals")
    preset = models.ForeignKey(ThemePreset, on_delete=models.CASCADE, help_text="Theme to switch on during these dates.")
    label = models.CharField(max_length=60, blank=True, help_text="e.g. 'Diwali 2026'.")
    start_date = models.DateField(help_text="First day the festival look appears.")
    end_date = models.DateField(help_text="Last day the festival look appears.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["start_date"]
        verbose_name = "Scheduled festival"

    def __str__(self):
        return self.label or f"{self.preset} ({self.start_date} → {self.end_date})"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("The end date must be on or after the start date.")


# ---------------------------------------------------------------------------
# 3. Homepage Builder
# ---------------------------------------------------------------------------
LINK_HELP = ("Where it goes: #catalog (scroll to products), /p/product-slug, a full https:// link, "
             "'whatsapp' (WhatsApp chat), 'enquire' (enquiry form) or 'enquire:hotel' / 'enquire:corporate'.")


class HeroSlide(ScheduleMixin, DesignFields):
    class TextTone(models.TextChoices):
        AUTO = "auto", "Automatic (theme colours)"
        DARK = "dark", "Dark text (for light photos)"
        LIGHT = "light", "White text (for dark photos)"

    class Size(models.TextChoices):
        S = "s", "Small"
        M = "m", "Medium"
        L = "l", "Large"
        XL = "xl", "Extra large"

    class Height(models.TextChoices):
        FULL = "full", "Full screen"
        LARGE = "large", "Large (80% of screen)"
        MEDIUM = "medium", "Medium (60% of screen)"

    layout = models.CharField(max_length=24, choices=D.choices(D.HERO_LAYOUTS), default="cinematic",
                              help_text="The overall look of this hero. 24 layouts — see the live preview on the right.")
    eyebrow = models.CharField(max_length=80, blank=True, help_text="Small line above the headline. Leave empty to show your brand tagline; "
                                                                   "type a single dash (-) to hide it.")
    headline = models.CharField(max_length=120, help_text="Big headline. Keep it short and calm — 3 to 8 words.")
    subheadline = models.CharField(max_length=220, blank=True, help_text="One supporting sentence under the headline.")
    headline_size = models.CharField(max_length=2, choices=Size.choices, default=Size.L)
    text_tone = models.CharField(max_length=6, choices=TextTone.choices, default=TextTone.AUTO,
                                 help_text="Pick white text when your photo/video is dark.")
    overlay_strength = models.PositiveSmallIntegerField(default=40, validators=[MaxValueValidator(90)],
                                                        help_text="How much soft veil sits over the media so words stay readable (0–90).")
    height = models.CharField(max_length=6, choices=Height.choices, default=Height.FULL)

    video_desktop = models.FileField(upload_to="hero/", blank=True, help_text="MP4/WebM for computers. Under 8 MB, 10–20 seconds, no sound.")
    video_mobile = models.FileField(upload_to="hero/", blank=True, help_text="Lighter MP4 for phones. Under 3 MB, vertical or square.")
    poster_image = models.ImageField(upload_to="hero/", blank=True, help_text="Main picture (also shown while the video loads and on slow phones).")

    cta_text = models.CharField(max_length=40, default="Explore Essentials", blank=True, help_text="Main button label (empty = no button).")
    cta_link = models.CharField(max_length=300, default="#catalog", help_text=LINK_HELP)
    secondary_cta_text = models.CharField(max_length=40, default="Bulk Enquiry on WhatsApp", blank=True,
                                          help_text="Second button label (empty = no second button).")
    secondary_cta_link = models.CharField(max_length=300, default="whatsapp", blank=True, help_text=LINK_HELP)
    show_product = models.BooleanField(default=True, help_text="Show a small floating product card (layouts that support it).")
    product = models.ForeignKey("catalog.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
                                help_text="Which product to feature. Empty = your first featured product.")

    order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, help_text="Untick to hide this slide.")

    class Meta:
        ordering = ["order"]
        verbose_name = "Hero slide"

    def __str__(self):
        return self.headline

    def save(self, *args, **kwargs):
        compress_image_field(self.poster_image, max_side=2400)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"{settings.SITE_URL}/"


class HeroMedia(MediaItemBase):
    slide = models.ForeignKey(HeroSlide, on_delete=models.CASCADE, related_name="media")

    class Meta(MediaItemBase.Meta):
        verbose_name = "Extra photo / video"
        verbose_name_plural = "Extra photos & videos (they rotate)"


class PageSection(ScheduleMixin, DesignFields):
    class MediaPosition(models.TextChoices):
        AUTO = "auto", "Automatic (alternates)"
        LEFT = "left", "Media on the left"
        RIGHT = "right", "Media on the right"

    class SectionType(models.TextChoices):
        HERO_BANNER = "hero_banner", "Animated Hero Banner (any of the 24 hero layouts)"
        GALLERY = "gallery", "Media Gallery (rotating photos & videos)"
        MARQUEE_TEXT = "marquee_text", "Big Moving Text"
        VIDEO_SHOWCASE = "video_showcase", "Video Showcase"
        EDITORIAL = "editorial", "Editorial Text + Image"
        PROMO_BANNER = "promo_banner", "Promo Banner"
        BRAND_STORY = "brand_story", "Brand Story"
        FEATURED_COLLECTION = "featured_collection", "Featured Collection"
        CATEGORY_GRID = "category_grid", "Category Grid"
        INGREDIENT_SPOTLIGHT = "ingredient_spotlight", "Ingredient Spotlight"
        ROUTINE_BUILDER = "routine_builder", "Routine Builder (Morning / Night)"
        PRODUCT_GUIDE = "product_guide", "Bristle & Product Guide (comparison)"
        FREE_FROM = "free_from", "Free-From & Certifications Strip"
        SUSTAINABILITY = "sustainability", "Sustainability Story"
        TESTIMONIALS = "testimonials", "Testimonials"
        FOR_BUSINESS = "for_business", "For Business (B2B)"
        FAQ = "faq", "FAQ"
        UGC_STRIP = "ugc_strip", "Instagram / UGC Strip"

    class Background(models.TextChoices):
        SURFACE = "surface", "Page colour"
        ELEVATED = "elevated", "White card"
        PRIMARY_TINT = "primary_tint", "Soft primary tint"
        SECONDARY_TINT = "secondary_tint", "Soft secondary tint"
        INK = "ink", "Dark (deep ink)"

    section_type = models.CharField(max_length=30, choices=SectionType.choices, db_index=True,
                                    help_text="What kind of block this is. Each type has its own layout.")
    eyebrow = models.CharField(max_length=60, blank=True, help_text="Tiny label above the title, e.g. 'OUR STORY'.")
    title = models.CharField(max_length=140, blank=True, help_text="Section headline.")
    body = models.TextField(blank=True, help_text="Main text. Leave a blank line between paragraphs.")
    image = models.ImageField(upload_to="sections/", blank=True, help_text="Main picture for this section.")
    video = models.FileField(upload_to="sections/", blank=True, help_text="Optional MP4 video (under 8 MB).")
    cta_text = models.CharField(max_length=40, blank=True, help_text="Button label (optional).")
    cta_link = models.CharField(max_length=300, blank=True, help_text=LINK_HELP)
    background_style = models.CharField(max_length=20, choices=Background.choices, default=Background.SURFACE)
    hero_layout = models.CharField(max_length=24, choices=D.choices(D.HERO_LAYOUTS), default="split_shape",
                                   help_text="Only for 'Animated Hero Banner': which of the 24 hero layouts to use.")
    media_position = models.CharField(max_length=6, choices=MediaPosition.choices, default=MediaPosition.AUTO,
                                      help_text="For sections with words + media side by side.")
    category = models.ForeignKey("catalog.Category", on_delete=models.SET_NULL, null=True, blank=True,
                                 help_text="For 'Featured Collection': show products from this category. Leave empty for featured products.")
    items = models.JSONField(default=list, blank=True,
                             help_text="Extra list content for this section (FAQ questions, testimonials, routine steps…). "
                                       "Easiest to edit using the 'Items' helper below; see the guide for each type.")
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, help_text="Untick to hide this section.")

    class Meta:
        ordering = ["order"]
        verbose_name = "Page section"

    def __str__(self):
        return f"{self.get_section_type_display()} — {self.title or 'untitled'}"

    def save(self, *args, **kwargs):
        compress_image_field(self.image, max_side=2000)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"{settings.SITE_URL}/#section-{self.pk}"


class SectionMedia(MediaItemBase):
    section = models.ForeignKey(PageSection, on_delete=models.CASCADE, related_name="media")

    class Meta(MediaItemBase.Meta):
        verbose_name = "Extra photo / video"
        verbose_name_plural = "Extra photos & videos (they rotate)"


# ---------------------------------------------------------------------------
# 4. Site Design Studio — the look & motion of the whole site
# ---------------------------------------------------------------------------
class SiteDesign(SingletonModel):
    class HeaderStyle(models.TextChoices):
        FLOATING_PILL = "floating_pill", "Floating glass pill"
        FULL_BAR = "full_bar", "Full-width bar"
        MINIMAL = "minimal", "Minimal (transparent, no box)"
        CENTERED = "centered", "Centered logo, links below"
        SPLIT = "split", "Logo centre, links left & actions right"

    class HeaderScroll(models.TextChoices):
        SHRINK = "shrink", "Shrinks a little"
        HIDE = "hide", "Hides when scrolling down, returns when scrolling up"
        STATIC = "static", "Always the same"
        SOLID = "solid", "Turns solid after scrolling"

    class Spacing(models.TextChoices):
        TIGHT = "0.04em", "Tight"
        NORMAL = "0.12em", "Normal"
        WIDE = "0.2em", "Wide (signature)"
        EXTRA = "0.35em", "Extra wide"

    class NavHover(models.TextChoices):
        PILL = "pill", "Soft pill"
        UNDERLINE = "underline", "Growing underline"
        GLOW = "glow", "Colour glow"
        LIFT = "lift", "Lift"

    class Announce(models.TextChoices):
        STATIC = "static", "Still"
        MARQUEE = "marquee", "Scrolling ticker"
        ROTATE = "rotate", "Rotating messages"

    class FooterStyle(models.TextChoices):
        INK = "ink", "Dark (deep ink)"
        LIGHT = "light", "Light (page colour)"
        PRIMARY = "primary", "Soft primary tint"
        GRADIENT = "gradient", "Theme gradient"
        GLASS = "glass", "Frosted glass"

    class WordSize(models.TextChoices):
        HIDDEN = "hidden", "Hidden"
        S = "s", "Small"
        M = "m", "Medium"
        L = "l", "Large"
        GIANT = "giant", "Giant (full width)"

    class WordAnim(models.TextChoices):
        NONE = "none", "Still"
        RISE = "rise", "Rises into view"
        LETTERS = "letters", "Letters rise one by one"
        MARQUEE = "marquee", "Scrolls endlessly"
        OUTLINE = "outline", "Outline that fills on hover"
        SHIMMER = "shimmer", "Shimmering light"
        PARALLAX = "parallax", "Moves with scroll"
        WAVE = "wave", "Letters wave"
        FOLLOW = "follow", "Letters lift near the mouse"

    class ButtonShape(models.TextChoices):
        PILL = "999px", "Pill"
        ROUNDED = "16px", "Rounded"
        SOFT = "8px", "Soft"
        SQUARE = "0px", "Square"
        LEAF = "4px 20px 4px 20px", "Leaf"

    class ButtonHover(models.TextChoices):
        LIFT = "lift", "Lift"
        GLOW = "glow", "Glow"
        FILL = "fill", "Colour fill sweep"
        SHINE = "shine", "Light shine"
        MAGNETIC = "magnetic", "Magnetic"
        NONE = "none", "Nothing"

    class CardStyle(models.TextChoices):
        MINIMAL = "minimal", "Minimal (photo + text)"
        BORDERED = "bordered", "Fine border"
        ELEVATED = "elevated", "White card with shadow"
        GLASS = "glass", "Frosted glass"
        TINTED = "tinted", "Soft colour tint"

    class Aspect(models.TextChoices):
        PORTRAIT = "4 / 5", "Portrait 4:5"
        TALL = "3 / 4", "Tall 3:4"
        EXTRA_TALL = "2 / 3", "Extra tall 2:3"
        SQUARE = "1 / 1", "Square 1:1"
        WIDE = "4 / 3", "Landscape 4:3"

    class ImageHover(models.TextChoices):
        CROSSFADE = "crossfade", "Show 2nd photo"
        ZOOM = "zoom", "Zoom"
        BOTH = "both", "2nd photo + zoom"
        NONE = "none", "Nothing"

    class Cursor(models.TextChoices):
        DEFAULT = "default", "Normal mouse pointer"
        DOT = "dot", "Soft dot that trails the mouse"
        RING = "ring", "Ring + dot"
        BLEND = "blend", "Inverting bubble"
        GLOW = "glow", "Colour glow"
        TRAIL = "trail", "Bubble trail"

    class Loader(models.TextChoices):
        PULSE = "pulse", "Pulsing wordmark"
        LETTERS = "letters", "Letters rise"
        CURTAIN = "curtain", "Curtain lifts"
        NONE = "none", "None"

    class DockPos(models.TextChoices):
        RIGHT = "right", "Bottom right"
        LEFT = "left", "Bottom left"
        CENTER = "center", "Bottom centre"

    # Motion & defaults
    default_media_shape = models.CharField(max_length=20, choices=D.choices(D.SHAPES), default="rounded",
                                           help_text="Shape used for photos/videos unless a section picks its own.")
    default_entrance = models.CharField(max_length=20, choices=D.choices(D.ENTRANCES), default="fade_up")
    default_text_animation = models.CharField(max_length=20, choices=D.choices(D.TEXT_ANIMATIONS), default="rise_words")
    default_hover = models.CharField(max_length=20, choices=D.choices(D.HOVER_EFFECTS), default="lift")
    default_media_motion = models.CharField(max_length=20, choices=D.choices(D.MEDIA_MOTIONS), default="none")
    default_gallery_style = models.CharField(max_length=20, choices=D.choices(D.GALLERY_STYLES), default="fade")
    default_pointer = models.CharField(max_length=20, choices=D.choices(D.POINTER_EFFECTS), default="none")
    default_decor = models.CharField(max_length=20, choices=D.choices(D.DECOR_SHAPES), default="none")
    default_divider = models.CharField(max_length=20, choices=D.choices(D.DIVIDERS), default="none")
    animation_speed = models.CharField(max_length=10, choices=D.choices(D.SPEEDS), default="normal")
    cursor_style = models.CharField(max_length=10, choices=Cursor.choices, default=Cursor.DEFAULT,
                                    help_text="Custom mouse cursor on computers (phones are never affected).")
    scroll_progress = models.BooleanField(default=False, help_text="Thin bar at the top that fills as visitors scroll.")
    smooth_scroll = models.BooleanField(default=True, help_text="Buttery smooth scrolling on computers.")
    page_loader = models.CharField(max_length=10, choices=Loader.choices, default=Loader.PULSE,
                                   help_text="What visitors see for a moment while the site loads.")

    # Buttons
    button_shape = models.CharField(max_length=20, choices=ButtonShape.choices, default=ButtonShape.PILL)
    button_hover = models.CharField(max_length=10, choices=ButtonHover.choices, default=ButtonHover.LIFT)

    # Header
    header_style = models.CharField(max_length=16, choices=HeaderStyle.choices, default=HeaderStyle.FLOATING_PILL)
    header_scroll = models.CharField(max_length=10, choices=HeaderScroll.choices, default=HeaderScroll.SHRINK)
    header_entrance = models.CharField(max_length=20, choices=D.choices(D.ENTRANCES), default="fade_down")
    header_wordmark_size = models.PositiveSmallIntegerField(default=22, validators=[MinValueValidator(12), MaxValueValidator(64)],
                                                            help_text="Size of the PAALVI name in the header, in pixels (12–64).")
    wordmark_spacing = models.CharField(max_length=8, choices=Spacing.choices, default=Spacing.WIDE,
                                        help_text="Gap between the letters of the PAALVI name.")
    nav_hover = models.CharField(max_length=10, choices=NavHover.choices, default=NavHover.PILL)
    show_search = models.BooleanField(default=True)
    show_tier_toggle = models.BooleanField(default=True, verbose_name="Show Retail / Wholesale switch")
    show_ai_button = models.BooleanField(default=True, verbose_name="Show AI guide button in header")
    announcement_style = models.CharField(max_length=10, choices=Announce.choices, default=Announce.STATIC)

    # Footer
    footer_style = models.CharField(max_length=10, choices=FooterStyle.choices, default=FooterStyle.INK)
    footer_wordmark_text = models.CharField(max_length=40, blank=True,
                                            help_text="The big word at the bottom of the footer. Empty = your brand name.")
    footer_wordmark_size = models.CharField(max_length=6, choices=WordSize.choices, default=WordSize.L)
    footer_wordmark_animation = models.CharField(max_length=10, choices=WordAnim.choices, default=WordAnim.RISE)
    footer_decor = models.CharField(max_length=20, choices=D.choices(D.DECOR_SHAPES), default="none")
    footer_divider = models.CharField(max_length=20, choices=D.choices(D.DIVIDERS), default="none",
                                      help_text="Shape of the footer's top edge.")
    footer_legal_text = models.CharField(max_length=240, blank=True,
                                         default="All prices are MRP / selling prices in ₹, inclusive of all taxes.",
                                         help_text="Small print after © year and brand name.")
    footer_show_socials = models.BooleanField(default=True)

    # Product cards
    card_style = models.CharField(max_length=10, choices=CardStyle.choices, default=CardStyle.MINIMAL)
    card_image_shape = models.CharField(max_length=20, choices=D.choices(D.SHAPES), default="soft")
    card_aspect = models.CharField(max_length=8, choices=Aspect.choices, default=Aspect.PORTRAIT)
    card_hover = models.CharField(max_length=20, choices=D.choices(D.HOVER_EFFECTS), default="tilt_3d")
    card_image_hover = models.CharField(max_length=10, choices=ImageHover.choices, default=ImageHover.BOTH)
    card_entrance = models.CharField(max_length=20, choices=D.choices(D.ENTRANCES), default="fade_up")
    card_show_whatsapp = models.BooleanField(default=True, help_text="Small WhatsApp button on each product card.")
    product_gallery_shape = models.CharField(max_length=20, choices=D.choices(D.SHAPES), default="rounded",
                                             help_text="Shape of the big photos on the product page.")

    # Floating buttons
    show_contact_dock = models.BooleanField(default=True, help_text="Floating WhatsApp + socials dock.")
    dock_position = models.CharField(max_length=8, choices=DockPos.choices, default=DockPos.RIGHT)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site design studio"
        verbose_name_plural = "Site design studio"

    def __str__(self):
        return "Site design"

    def get_absolute_url(self):
        return f"{settings.SITE_URL}/"

    def payload(self):
        skip = {"id", "updated_at"}
        return {f.name: getattr(self, f.name) for f in self._meta.concrete_fields if f.name not in skip}


class NavLink(models.Model):
    label = models.CharField(max_length=40, help_text="Text in the header menu, e.g. 'Shop'.")
    link = models.CharField(max_length=300, help_text=LINK_HELP + " Section anchors: #ritual, #business, #faq or #section-ID.")
    highlight = models.BooleanField(default=False, help_text="Show as a filled button instead of a plain link.")
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "Header menu link"

    def __str__(self):
        return self.label


class FooterColumn(models.Model):
    class Kind(models.TextChoices):
        LINKS = "links", "My own links (add them below)"
        CATEGORIES = "categories", "Product categories (automatic) + my links"
        CONTACT = "contact", "Contact details (automatic) + my links"

    title = models.CharField(max_length=40, help_text="Small heading above the column, e.g. 'Shop'.")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.LINKS)
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "Footer column"

    def __str__(self):
        return self.title


class FooterLink(models.Model):
    column = models.ForeignKey(FooterColumn, on_delete=models.CASCADE, related_name="links")
    label = models.CharField(max_length=60, help_text="e.g. 'Hotel amenity kits' or 'sales@paalvi.in'.")
    link = models.CharField(max_length=300, help_text=LINK_HELP + " Emails: mailto:sales@paalvi.in · Phone: tel:+919876543210.")
    icon = models.CharField(max_length=30, blank=True, help_text="Optional icon name: mail, phone, map, whatsapp, hotel, gift, store…")
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "Link"

    def __str__(self):
        return self.label


# ---------------------------------------------------------------------------
# 6. AI Concierge
# ---------------------------------------------------------------------------
class AIAssistantConfig(SingletonModel):
    class Tone(models.TextChoices):
        WARM = "warm", "Warm & friendly"
        CLINICAL = "clinical", "Clear & clinical"
        PLAYFUL = "playful", "Light & playful"

    is_active = models.BooleanField(default=True, help_text="Untick to hide the AI guide from the website.")
    assistant_name = models.CharField(max_length=40, default="Paalvi Care Guide")
    welcome_greeting = models.TextField(default="Hi! I'm your Paalvi Care Guide. Tell me what your smile needs — sensitive gums, whitening, kids, or bulk orders — and I'll suggest the right essentials.")
    quick_prompts = models.JSONField(
        default=list, blank=True,
        help_text='Suggestion chips shown to visitors. One per line in the list, e.g. ["Fluoride-free options", "Gift sets"].',
    )
    brand_knowledge = models.TextField(blank=True, help_text="What makes Paalvi special — the AI uses this to answer brand questions.")
    shipping_info = models.TextField(blank=True, help_text="Delivery areas, timelines and charges.")
    returns_info = models.TextField(blank=True, help_text="Returns & replacement policy in plain words.")
    b2b_info = models.TextField(blank=True, help_text="Wholesale terms: MOQ, private label, GST invoices, delivery for businesses.")
    tone = models.CharField(max_length=10, choices=Tone.choices, default=Tone.WARM)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI Care Guide settings"
        verbose_name_plural = "AI Care Guide settings"

    def __str__(self):
        return self.assistant_name
