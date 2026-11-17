"""
python manage.py seed_themes

Creates (or refreshes) the 24 curated Paalvi theme presets: 12 everyday + 12 festival.
Safe to run again — existing presets are updated by name, your custom ones are untouched.
"""

from django.core.management.base import BaseCommand

from storefront.models import ActiveTheme, ThemePreset
from storefront.utils import clear_site_cache

# name, kind, description, primary, secondary, accent, surface, surface_elevated, text, text_muted, font, ambient
PRESETS = [
    # ---- Everyday (12) ----
    ("Paalvi Fresh", "everyday", "The signature look — porcelain, seafoam and clay.",
     "#8FC9B9", "#E6CFC3", "#BFA77A", "#F8F7F4", "#FFFFFF", "#14181F", "#5B6470", "instrument", "bubbles"),
    ("Porcelain Pure", "everyday", "Almost-white, gallery calm.",
     "#C9D6D3", "#ECE7E1", "#A89A7E", "#FBFAF8", "#FFFFFF", "#15171A", "#5E636B", "instrument", "none"),
    ("Mint Clinic", "everyday", "Crisp, clinical freshness.",
     "#7CCFC0", "#DCEFEA", "#4C9E8F", "#F4FAF8", "#FFFFFF", "#0F1E1C", "#4B5F5B", "instrument", "bubbles"),
    ("Charcoal Detox", "everyday", "Dark and moody for the charcoal range.",
     "#9ED9C8", "#3A3F45", "#C9B48A", "#16181B", "#202327", "#F2F1EE", "#A9AEB4", "fraunces", "mist"),
    ("Bamboo Earth", "everyday", "Warm natural fibres and sage.",
     "#A7B98A", "#E9DCC6", "#9C7B4F", "#F7F3EA", "#FFFDF8", "#22201A", "#625B4C", "fraunces", "petals"),
    ("Pearl White", "everyday", "Soft pearl with a champagne glint.",
     "#D8CFE0", "#EFE8E1", "#BFA77A", "#FAF8F6", "#FFFFFF", "#1A1820", "#5F5B66", "instrument", "bubbles"),
    ("Arctic Blue", "everyday", "Cool, icy and clean.",
     "#9CC7E4", "#E3EEF6", "#6C93B3", "#F5F9FC", "#FFFFFF", "#0F1A24", "#4D5D6B", "instrument", "ripple"),
    ("Clay & Sage", "everyday", "Earthy clay meets herbal sage.",
     "#A9C2A5", "#E6CFC3", "#B98463", "#F7F2EE", "#FFFFFF", "#1E1B18", "#5F5751", "fraunces", "none"),
    ("Midnight Mint", "everyday", "Deep navy with a mint glow.",
     "#8FE0C8", "#24314A", "#D7C08D", "#0F1626", "#182134", "#EEF3F7", "#A3B0C2", "instrument", "bubbles"),
    ("Herbal Neem", "everyday", "Leafy greens for the herbal range.",
     "#7FB77E", "#E2EBD4", "#B5A160", "#F5F8F0", "#FFFFFF", "#17200F", "#536049", "fraunces", "petals"),
    ("Saffron Ayurveda", "everyday", "Turmeric warmth and ayurvedic calm.",
     "#E7B567", "#F3E2C7", "#B0742E", "#FBF6EE", "#FFFFFF", "#22180C", "#665742", "tiro", "mist"),
    ("Sea Salt Coast", "everyday", "Breezy coastal blues and sand.",
     "#8EC5C7", "#E9E1D3", "#C2A272", "#F6F7F5", "#FFFFFF", "#132022", "#526366", "instrument", "ripple"),
    # ---- Festival (12) ----
    ("Diwali Royal Gold", "festival", "Deep aubergine night lit with gold diyas.",
     "#E2B45A", "#5B2A4A", "#F3D28B", "#1C1020", "#2A1830", "#FBF3E6", "#D3C2B4", "tiro", "diyas"),
    ("Holi Prism", "festival", "Joyful gulal colours on bright white.",
     "#F2709C", "#FFD36E", "#6DC6E7", "#FFFBF7", "#FFFFFF", "#1E1420", "#5E4F60", "fraunces", "gulal"),
    ("Eid Emerald & Pearl", "festival", "Emerald night with pearl and moonlight.",
     "#7BD3B1", "#1E4A40", "#E5D3A1", "#0E2621", "#14332C", "#F3F1EA", "#B5C4BD", "fraunces", "diyas"),
    ("Navratri Nine Nights", "festival", "Vibrant garba energy.",
     "#E8507A", "#FFC145", "#3BB4A6", "#FFF8F1", "#FFFFFF", "#24131A", "#644E55", "tiro", "gulal"),
    ("Raksha Bandhan Silk", "festival", "Silk threads of rose and saffron.",
     "#E8A0A8", "#F7DCC4", "#C99A4B", "#FDF6F3", "#FFFFFF", "#26161A", "#66545A", "fraunces", "petals"),
    ("Pongal / Sankranti Harvest", "festival", "Sugarcane green, harvest gold and kolam white.",
     "#9CBF5F", "#F5DE9C", "#C8862F", "#FBF8EF", "#FFFFFF", "#1E1F12", "#5C5B45", "tiro", "petals"),
    ("Onam Kasavu", "festival", "Ivory kasavu with a golden border.",
     "#D9B45A", "#F2E9D2", "#A8812E", "#FCFAF3", "#FFFFFF", "#201B0F", "#605842", "tiro", "petals"),
    ("Durga Puja Alta Red", "festival", "Red-bordered white sari and alta red.",
     "#D2423B", "#F4D9C9", "#C79A3E", "#FCF7F3", "#FFFFFF", "#22110F", "#634A45", "tiro", "petals"),
    ("Christmas Velvet & Frost", "festival", "Velvet green with frosty snow.",
     "#C94A4A", "#1F3B32", "#D9C08A", "#10211C", "#173029", "#F4F2EC", "#B9C3BD", "fraunces", "snow"),
    ("New Year Champagne", "festival", "Midnight black and champagne sparkle.",
     "#E4C98F", "#2C2A2F", "#F2E2B8", "#121114", "#1C1B1F", "#F7F3EA", "#B8B2A6", "instrument", "diyas"),
    ("Independence Tricolor Luxe", "festival", "Saffron, white and green — refined.",
     "#F08A3C", "#E3F0E2", "#2E8B57", "#FCFBF8", "#FFFFFF", "#141A2B", "#545B6B", "instrument", "petals"),
    ("Wedding Season Blush & Gold", "festival", "Blush pink and gilded gold for gifting season.",
     "#E7B3B5", "#F6E6DC", "#C29A55", "#FDF8F5", "#FFFFFF", "#24171A", "#65555A", "fraunces", "petals"),
]


class Command(BaseCommand):
    help = "Create the 24 curated Paalvi theme presets (12 everyday + 12 festival)."

    def handle(self, *args, **opts):
        created = 0
        for i, row in enumerate(PRESETS):
            (name, kind, desc, primary, secondary, accent, surface, elevated, text, muted, font, ambient) = row
            _, was_created = ThemePreset.objects.update_or_create(
                name=name,
                defaults=dict(
                    kind=kind, description=desc, primary=primary, secondary=secondary, accent=accent, surface=surface,
                    surface_elevated=elevated, text=text, text_muted=muted, display_font=font, ambient_effect=ambient,
                    order=i,
                ),
            )
            created += was_created
        at = ActiveTheme.load()
        if not at.default_preset_id:
            at.default_preset = ThemePreset.objects.get(name="Paalvi Fresh")
            at.save()
        warnings = [(p.name, w) for p in ThemePreset.objects.all() for w in p.contrast_warnings()]
        for name, w in warnings:
            self.stdout.write(self.style.WARNING(f"{name}: {w}"))
        clear_site_cache()
        self.stdout.write(self.style.SUCCESS(f"Themes ready: {created} created, {len(PRESETS) - created} refreshed."))
