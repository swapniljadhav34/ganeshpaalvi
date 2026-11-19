"""
Admin screens for Brand, Theme & Festival Studio, Homepage Builder and AI Concierge.
Written for a business owner: friendly labels, previews, no jargon.
"""

import json

from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action, display
from unfold.widgets import UnfoldAdminColorInputWidget

from .utils import brand_name
from .models import (
    UiTranslation,
    ActiveTheme,
    AIAssistantConfig,
    BrandSettings,
    FestivalSchedule,
    FooterColumn,
    FooterLink,
    HeroMedia,
    HeroSlide,
    NavLink,
    PageSection,
    SectionMedia,
    SiteDesign,
    ThemePreset,
)
from .preview import preview_panel

COLOR_FIELDS = ["primary", "secondary", "accent", "surface", "surface_elevated", "text", "text_muted"]


class SingletonAdmin(ModelAdmin):
    """Opens the single settings row directly instead of showing a list."""

    def has_add_permission(self, request):
        return not self.model.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = self.model.load()
        opts = self.model._meta
        return redirect(reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk]))


def view_on_site_link(url, label="View on site ↗"):
    return format_html('<a href="{}" target="_blank" rel="noopener" class="text-primary-600 font-semibold">{}</a>', url, label)


# ---------------------------------------------------------------------------
@admin.register(BrandSettings)
class BrandSettingsAdmin(SingletonAdmin):
    fieldsets = (
        ("Brand", {"fields": ("brand_name", "tagline", "logo_dark", "logo_light", "favicon")}),
        ("How customers reach you", {"fields": ("whatsapp_number", "contact_email", "phone",
                                                "instagram_url", "facebook_url", "x_url")}),
        ("Announcement bar (top of site)", {"fields": ("announcement_active", "announcement_text", "announcement_more", "announcement_link")}),
        ("Business & legal details", {"fields": ("registered_address", "google_maps_link", "gstin", "manufacturer_details",
                                                 "marketer_details", "customer_care_details"), "classes": ["tab"]}),
        ("Footer & Google", {"fields": ("footer_story", "default_seo_title", "default_seo_description", "og_share_image")}),
        ("Privacy policy", {"fields": ("privacy_policy",), "classes": ["tab"],
                            "description": "Shown at /privacy and linked from every enquiry form."}),
    )


# ---------------------------------------------------------------------------
class ThemePresetForm(forms.ModelForm):
    class Meta:
        model = ThemePreset
        fields = "__all__"
        widgets = {name: UnfoldAdminColorInputWidget for name in COLOR_FIELDS}


def swatch_html(p, size=22):
    """Little row of colour dots — a visual 'swatch card' for a preset."""
    dots = format_html_join(
        "",
        '<span title="{}" style="display:inline-block;width:{}px;height:{}px;border-radius:999px;background:{};'
        'border:1px solid rgba(0,0,0,.12);margin-right:4px"></span>',
        ((name, size, size, getattr(p, name)) for name in ["surface", "primary", "secondary", "accent", "text"]),
    )
    return format_html('<span style="display:inline-flex;align-items:center">{}</span>', dots)


@admin.register(ThemePreset)
class ThemePresetAdmin(ModelAdmin):
    form = ThemePresetForm
    list_display = ["name", "swatches", "kind", "ambient_effect", "contrast_badge", "is_live"]
    list_filter = ["kind", "ambient_effect"]
    search_fields = ["name"]
    ordering_field = "order"
    hide_ordering_field = True
    readonly_fields = ["live_preview"]
    prepopulated_fields = {"slug": ["name"]}
    actions_detail = ["make_live"]
    actions = ["make_live_bulk"]
    fieldsets = (
        (None, {"fields": ("name", "slug", "kind", "description")}),
        ("Colours", {"fields": (("primary", "secondary", "accent"), ("surface", "surface_elevated"), ("text", "text_muted"),
                                "live_preview")}),
        ("Typography & motion", {"fields": ("display_font", "ambient_effect", "preview_image")}),
    )

    @display(description="Colours")
    def swatches(self, obj):
        return swatch_html(obj)

    @display(description="Readability", label={"Easy to read": "success", "Check contrast": "warning"})
    def contrast_badge(self, obj):
        return "Check contrast" if obj.contrast_warnings() else "Easy to read"

    @display(description="Live now", boolean=True)
    def is_live(self, obj):
        preset, _ = ActiveTheme.load().resolve()
        return preset and preset.pk == obj.pk

    @display(description="Live preview")
    def live_preview(self, obj):
        # Updates instantly while you change colour pickers (small script below).
        p = obj if obj and obj.pk else ThemePreset()
        warnings = p.contrast_warnings()
        warn_html = format_html_join("", '<li style="color:#b45309">⚠ {}</li>', ((w,) for w in warnings)) if warnings else \
            format_html('<li style="color:#15803d">✓ Text is easy to read on this background (WCAG AA).</li>')
        return format_html(
            """
<div id="paalvi-theme-preview" style="border-radius:20px;padding:28px;max-width:520px;background:{surface};color:{text};
     border:1px solid rgba(0,0,0,.08);font-family:Georgia,serif">
  <div style="font-size:11px;letter-spacing:.2em;color:{muted};font-family:system-ui">{brand}</div>
  <div style="font-size:30px;line-height:1.1;margin:10px 0">Everyday essentials, elevated.</div>
  <div style="font-family:system-ui;font-size:14px;color:{muted}">Soft bamboo bristles · Fluoride-free</div>
  <div style="display:flex;gap:10px;margin-top:18px;font-family:system-ui">
    <span data-k="primary" style="background:{primary};color:{text};padding:10px 18px;border-radius:999px;font-size:13px">Explore</span>
    <span data-k="secondary" style="background:{secondary};color:{text};padding:10px 18px;border-radius:999px;font-size:13px">Wholesale</span>
    <span data-k="card" style="background:{elevated};padding:10px 18px;border-radius:12px;font-size:13px;border:1px solid {accent}">₹149</span>
  </div>
</div>
<ul style="margin-top:10px;font-size:13px">{warnings}</ul>
<script>
(function(){{
  const box=document.getElementById('paalvi-theme-preview'); if(!box) return;
  const get=n=>{{const el=document.querySelector('[name="'+n+'"]');return el?el.value:null}};
  function paint(){{
    box.style.background=get('surface');box.style.color=get('text');
    box.querySelectorAll('div')[0].style.color=get('text_muted');box.querySelectorAll('div')[2].style.color=get('text_muted');
    box.querySelector('[data-k=primary]').style.background=get('primary');
    box.querySelector('[data-k=secondary]').style.background=get('secondary');
    const c=box.querySelector('[data-k=card]');c.style.background=get('surface_elevated');c.style.borderColor=get('accent');
  }}
  document.addEventListener('input',e=>{{if(e.target.name&&{fields}.includes(e.target.name))paint()}});
}})();
</script>""",
            surface=p.surface, text=p.text, muted=p.text_muted, primary=p.primary, secondary=p.secondary,
            elevated=p.surface_elevated, accent=p.accent, warnings=warn_html, brand=brand_name().upper(),
            fields=mark_safe(json.dumps(COLOR_FIELDS)),
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        for w in obj.contrast_warnings():
            messages.warning(request, f"Readability check for '{obj.name}': {w}")

    @action(description="Use this theme now", url_path="make-live", icon="bolt")
    def make_live(self, request, object_id):
        at = ActiveTheme.load()
        at.manual_override_id = object_id
        at.save()
        messages.success(request, "Done! This theme is now live on the website (manual override).")
        return redirect(reverse("admin:storefront_themepreset_change", args=[object_id]))

    @admin.action(description="Use the selected theme now")
    def make_live_bulk(self, request, queryset):
        first = queryset.first()
        if first:
            at = ActiveTheme.load()
            at.manual_override = first
            at.save()
            messages.success(request, f"'{first.name}' is now live on the website.")


class FestivalInline(TabularInline):
    model = FestivalSchedule
    extra = 0
    fields = ["label", "preset", "start_date", "end_date", "is_active"]
    autocomplete_fields = ["preset"]


@admin.register(ActiveTheme)
class ActiveThemeAdmin(SingletonAdmin):
    inlines = [FestivalInline]
    readonly_fields = ["live_now"]
    autocomplete_fields = ["default_preset", "manual_override"]
    fieldsets = (
        ("What's live right now", {"fields": ("live_now",)}),
        ("Choose your look", {"fields": ("default_preset", "manual_override", "enable_ambient_effects"),
                              "description": "Manual override always wins. Otherwise a scheduled festival (below) wins "
                                             "during its dates, and your everyday theme is used the rest of the year."}),
    )

    @display(description="Live theme")
    def live_now(self, obj):
        preset, why = obj.resolve()
        if not preset:
            return "No theme yet — run 'python manage.py seed_themes'."
        reason = {"manual": "manual override", "festival": "festival schedule", "default": "everyday theme",
                  "fallback": "first preset"}[why]
        return format_html("{} &nbsp;<strong>{}</strong> <span style='opacity:.7'>({})</span>", swatch_html(preset), preset.name, reason)


# ---------------------------------------------------------------------------
class MediaPreviewMixin:
    @display(description="Preview")
    def thumb(self, obj):
        img = getattr(obj, "poster_image", None) or getattr(obj, "image", None)
        if img:
            return format_html('<img src="{}" style="height:48px;width:72px;object-fit:cover;border-radius:8px">', img.url)
        if getattr(obj, "video", None):
            return "🎬 video"
        return "—"


class LivePreviewMixin:
    """Adds the floating 'Live preview' panel (the real website, updating as you type)."""

    preview_kind = "site"
    change_form_after_template = "admin/storefront/preview_after.html"

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        context["paalvi_preview"] = preview_panel(self.preview_kind, obj)
        return super().render_change_form(request, context, add=add, change=change, form_url=form_url, obj=obj)


DESIGN_HELP = ("Leave any option on “Use site default” to follow the Site Design Studio. "
               "Watch the live preview on the right — click ↻ Replay to see animations again.")
DESIGN_FIELDSET = ("Shape & animation", {
    "classes": ["tab"],
    "fields": ("media_shape", ("entrance_animation", "animation_speed"), "text_animation",
               ("hover_effect", "pointer_effect"), "media_motion", ("gallery_style", "gallery_interval"),
               ("decor_shape", "divider_shape")),
    "description": DESIGN_HELP,
})


class HeroMediaInline(MediaPreviewMixin, TabularInline):
    model = HeroMedia
    extra = 0
    fields = ["thumb", "image", "video", "caption", "link", "alt_text"]
    readonly_fields = ["thumb"]
    ordering_field = "order"
    hide_ordering_field = True
    tab = True


class SectionMediaInline(HeroMediaInline):
    model = SectionMedia


@admin.register(HeroSlide)
class HeroSlideAdmin(LivePreviewMixin, MediaPreviewMixin, ModelAdmin):
    preview_kind = "hero"
    list_display = ["thumb", "headline", "layout", "is_active", "show_from", "show_until", "site_link"]
    list_editable = ["is_active"]
    list_filter = ["layout", "is_active"]
    search_fields = ["headline", "subheadline"]
    ordering_field = "order"
    hide_ordering_field = True
    autocomplete_fields = ["product"]
    inlines = [HeroMediaInline]
    fieldsets = (
        ("Layout", {"classes": ["tab"], "fields": ("layout", ("height", "headline_size"), ("text_tone", "overlay_strength"))}),
        ("Words & buttons", {"classes": ["tab"], "fields": (
            "eyebrow", "headline", "subheadline", ("cta_text", "cta_link"), ("secondary_cta_text", "secondary_cta_link"),
            ("show_product", "product"))}),
        ("Main video & picture", {"classes": ["tab"], "fields": ("poster_image", "media_alt", "video_desktop", "video_mobile"),
                                  "description": "The main media. Add more photos/videos in the “Extra photos & videos” tab — "
                                                 "they rotate in the style you pick under Shape & animation."}),
        DESIGN_FIELDSET,
        ("Visibility", {"classes": ["tab"], "fields": ("is_active", ("show_from", "show_until"))}),
    )

    @display(description="")
    def site_link(self, obj):
        return view_on_site_link(obj.get_absolute_url())


SECTION_GUIDE = """
<b>What to put in “Items” for each section type</b> (leave empty to use smart defaults):<br>
• <b>FAQ</b>: [{"q": "Question?", "a": "Answer."}]<br>
• <b>Testimonials</b>: [{"quote": "…", "name": "Priya", "role": "Pune", "rating": 5}]<br>
• <b>Routine Builder</b>: {"morning": [{"title": "Brush", "text": "2 minutes", "product": "bamboo-brush-soft"}], "night": [...]}<br>
• <b>Product Guide</b>: [{"name": "Ultra-soft", "best_for": "Sensitive gums", "level": 1, "text": "…", "product": "slug"}]<br>
• <b>Ingredient Spotlight</b>: [{"name": "Neem", "benefit": "Naturally antibacterial"}] — or tick “spotlight” on Ingredients<br>
• <b>For Business</b>: [{"title": "Hotels", "text": "Amenity kits with your logo", "icon": "hotel"}]<br>
• <b>Brand / Sustainability Story</b>: [{"stat": "100%", "label": "Plastic-free packaging"}]<br>
• <b>Instagram / UGC</b>: [{"image": "https://…", "caption": "…", "link": "https://instagram.com/…"}]<br>
• <b>Big Moving Text</b>: ["Soft on gums", "Kind to earth", "Made in India"] — or leave empty to scroll the title<br>
• <b>Media Gallery</b> and <b>Animated Hero Banner</b>: no items needed — add photos/videos in the “Extra photos & videos” tab.
"""


@admin.register(PageSection)
class PageSectionAdmin(LivePreviewMixin, MediaPreviewMixin, ModelAdmin):
    preview_kind = "section"
    list_display = ["thumb", "section_type", "title", "background_style", "is_active", "site_link"]
    list_filter = ["section_type", "is_active"]
    list_editable = ["is_active"]
    search_fields = ["title", "body", "eyebrow"]
    ordering_field = "order"
    hide_ordering_field = True
    autocomplete_fields = ["category"]
    inlines = [SectionMediaInline]
    fieldsets = (
        ("Section", {"classes": ["tab"], "fields": ("section_type", "background_style", "hero_layout", "media_position")}),
        ("Words & button", {"classes": ["tab"], "fields": ("eyebrow", "title", "body", ("cta_text", "cta_link"))}),
        ("Main media", {"classes": ["tab"], "fields": ("image", "media_alt", "video"),
                        "description": "Add more photos/videos in the “Extra photos & videos” tab — they rotate automatically."}),
        DESIGN_FIELDSET,
        ("Extra content", {"classes": ["tab"], "fields": ("category", "items"), "description": SECTION_GUIDE}),
        ("Visibility", {"classes": ["tab"], "fields": ("is_active", ("show_from", "show_until"))}),
    )

    @display(description="")
    def site_link(self, obj):
        return view_on_site_link(obj.get_absolute_url())


# ---------------------------------------------------------------------------
@admin.register(SiteDesign)
class SiteDesignAdmin(LivePreviewMixin, SingletonAdmin):
    preview_kind = "site"
    fieldsets = (
        ("Motion & defaults", {"classes": ["tab"], "fields": (
            "default_media_shape", ("default_entrance", "animation_speed"), "default_text_animation",
            ("default_hover", "default_pointer"), ("default_media_motion", "default_gallery_style"),
            ("default_decor", "default_divider"), ("cursor_style", "page_loader"), ("scroll_progress", "smooth_scroll")),
            "description": "These are used everywhere unless a hero slide or section chooses its own."}),
        ("Header", {"classes": ["tab"], "fields": (
            ("header_style", "header_scroll"), "header_entrance", ("header_wordmark_size", "wordmark_spacing"),
            "nav_hover", ("show_search", "show_tier_toggle", "show_ai_button"), "announcement_style"),
            "description": "Edit the menu links under “Header menu links”. Logo and announcement text live in Brand & Contact."}),
        ("Footer", {"classes": ["tab"], "fields": (
            "footer_style", ("footer_wordmark_text", "footer_wordmark_size"), "footer_wordmark_animation",
            ("footer_decor", "footer_divider"), "footer_legal_text", "footer_show_socials"),
            "description": "Edit the footer's columns and links under “Footer columns”."}),
        ("Product cards", {"classes": ["tab"], "fields": (
            ("card_style", "card_aspect"), "card_image_shape", ("card_hover", "card_image_hover"), "card_entrance",
            "card_show_whatsapp", "product_gallery_shape")}),
        ("Buttons & floating dock", {"classes": ["tab"], "fields": (
            ("button_shape", "button_hover"), ("show_contact_dock", "dock_position"))}),
    )


@admin.register(NavLink)
class NavLinkAdmin(ModelAdmin):
    list_display = ["label", "link", "highlight", "is_active"]
    list_editable = ["link", "highlight", "is_active"]
    list_display_links = ["label"]
    ordering_field = "order"
    hide_ordering_field = True
    search_fields = ["label", "link"]


class FooterLinkInline(TabularInline):
    model = FooterLink
    extra = 1
    fields = ["label", "link", "icon"]
    ordering_field = "order"
    hide_ordering_field = True


@admin.register(FooterColumn)
class FooterColumnAdmin(ModelAdmin):
    list_display = ["title", "kind", "link_count", "is_active"]
    list_editable = ["is_active"]
    ordering_field = "order"
    hide_ordering_field = True
    search_fields = ["title", "links__label", "links__link"]
    inlines = [FooterLinkInline]

    @display(description="Links")
    def link_count(self, obj):
        return obj.links.count()


@admin.register(AIAssistantConfig)
class AIAssistantConfigAdmin(SingletonAdmin):
    fieldsets = (
        ("Assistant", {"fields": ("is_active", "assistant_name", "tone", "welcome_greeting", "quick_prompts")}),
        ("What the assistant knows", {
            "fields": ("brand_knowledge", "shipping_info", "returns_info", "b2b_info"),
            "description": "Write in plain words. The assistant also sees matching products automatically, "
                           "and is told never to invent prices or make medical claims.",
        }),
    )


@admin.register(UiTranslation)
class UiTranslationAdmin(ModelAdmin):
    list_display = ["language", "key", "text"]
    list_filter = ["language"]
    search_fields = ["key", "text"]
    list_editable = ["text"]
