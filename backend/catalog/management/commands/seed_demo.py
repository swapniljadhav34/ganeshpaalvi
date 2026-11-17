"""
python manage.py seed_demo [--reset]

Fills an empty site with believable demo content so you can see Paalvi working right away:
brand details, AI guide, badges, ingredients, categories, 16 products (with generated
placeholder photos), hero, homepage sections and festival dates.

Replace everything from the admin when your real photos and copy are ready.
"""

import io
import math
import random
from datetime import date
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from catalog.models import Badge, Category, Ingredient, PackageOption, Product, ProductImage, ProductVariant
from storefront.models import (
    ActiveTheme,
    AIAssistantConfig,
    BrandSettings,
    FestivalSchedule,
    HeroMedia,
    HeroSlide,
    PageSection,
    SectionMedia,
    ThemePreset,
)
from storefront.utils import clear_site_cache

BADGES = [
    ("Fluoride-free", "Made without fluoride."), ("SLS-free", "No sodium lauryl sulphate foaming agent."),
    ("Paraben-free", "No parabens."), ("Vegan", "No animal-derived ingredients."),
    ("Cruelty-free", "Never tested on animals."), ("Dentist-recommended", "Recommended by practising dentists."),
    ("Ayurvedic", "Rooted in traditional Ayurvedic ingredients."), ("Recyclable", "Packaging can be recycled."),
    ("BPA-free", "No BPA in plastic parts."),
]
INGREDIENTS = [
    ("Neem", "leaf", "Traditionally used for oral hygiene", True),
    ("Clove Oil", "flower", "Warm, comforting freshness", True),
    ("Activated Charcoal", "sparkles", "Helps lift surface stains", True),
    ("Peppermint", "wind", "Cool, long-lasting fresh breath", True),
    ("Moso Bamboo", "tree", "Fast-growing, compostable handle", False),
    ("Xylitol", "droplet", "Sugar-free sweetness", False),
    ("Aloe Vera", "sprout", "Soothing and gentle", False),
    ("Sea Salt", "waves", "Mineral-rich clean feel", False),
]
CATEGORIES = [
    ("Oral Care", None, "Everything for a clean, calm smile.", "sparkles"),
    ("Toothbrushes", "Oral Care", "Soft, honest brushes — bamboo and recycled.", "brush"),
    ("Bamboo", "Toothbrushes", "Compostable Moso bamboo handles.", "leaf"),
    ("Toothpaste", "Oral Care", "Gentle pastes and gels, free from the harsh stuff.", "droplet"),
    ("Floss & Interdental", "Oral Care", "For the spaces your brush can't reach.", "sparkle"),
    ("Mouthwash & Tongue Care", "Oral Care", "Alcohol-free rinses and copper tongue cleaners.", "waves"),
    ("Daily Essentials", None, "Soaps, travel kits and amenity sets.", "package"),
    ("Gift & Amenity Sets", "Daily Essentials", "Hotel kits and festive gift boxes.", "gift"),
]

# title, subtitle, category, mrp, retail, wholesale, moq, qty, unit, badges, ingredients, suitable, tags, flags, kind, tint
PRODUCTS = [
    ("Bamboo Charcoal Toothbrush", "Ultra-soft charcoal bristles, compostable handle", "Bamboo", 149, 129, 72, 144, 1, "pcs",
     ["Vegan", "BPA-free", "Recyclable"], ["Moso Bamboo", "Activated Charcoal"], ["adults", "sensitive"],
     "bamboo, charcoal, eco, soft", "featured bestseller", "brush", "#DCE9E4"),
    ("Kids Bamboo Brush — Little Smiles", "Tiny head, extra-soft bristles for ages 2–8", "Bamboo", 99, 89, 48, 144, 1, "pcs",
     ["Vegan", "BPA-free"], ["Moso Bamboo"], ["kids"], "kids, bamboo, soft", "new", "brush", "#F4E1D6"),
    ("Recycled Grip Toothbrush", "Soft tapered bristles, recycled-plastic handle", "Toothbrushes", 79, 69, 38, 288, 1, "pcs",
     ["BPA-free", "Recyclable"], [], ["adults"], "everyday, recycled", "bestseller", "brush", "#E3EEF6"),
    ("Sensitive Care Ultra-soft Brush", "10,000 micro-fine bristles for tender gums", "Toothbrushes", 179, 159, 92, 144, 1, "pcs",
     ["Dentist-recommended", "BPA-free"], [], ["adults", "sensitive"], "sensitive, gums, ultra-soft", "featured", "brush", "#ECE7F2"),
    ("Orthodontic V-Trim Brush", "V-shaped bristles that clean around braces", "Toothbrushes", 189, 169, 99, 144, 1, "pcs",
     ["Dentist-recommended", "BPA-free"], [], ["braces", "adults", "kids"], "braces, orthodontic", "", "brush", "#E7F0EC"),
    ("Neem & Clove Herbal Toothpaste", "Ayurvedic paste with neem and clove oil", "Toothpaste", 140, 125, 74, 72, 100, "g",
     ["Ayurvedic", "SLS-free", "Paraben-free", "Vegan"], ["Neem", "Clove Oil"], ["adults"], "herbal, ayurvedic, neem, clove",
     "featured bestseller", "tube", "#E2EBD4"),
    ("Charcoal Mint Whitening Gel", "Fluoride-free gel that lifts surface stains", "Toothpaste", 199, 179, 105, 72, 100, "g",
     ["Fluoride-free", "SLS-free", "Vegan", "Cruelty-free"], ["Activated Charcoal", "Peppermint"], ["adults"],
     "whitening, charcoal, stains, coffee", "featured", "tube", "#DAD9D6"),
    ("Sensitive Relief Toothpaste", "Gentle, low-abrasion formula for daily comfort", "Toothpaste", 175, 159, 94, 72, 100, "g",
     ["SLS-free", "Paraben-free", "Dentist-recommended"], ["Aloe Vera", "Xylitol"], ["adults", "sensitive"],
     "sensitive, gentle", "bestseller", "tube", "#EAF2F4"),
    ("Kids Strawberry Toothpaste", "Mild, fluoride-free paste kids actually like", "Toothpaste", 110, 99, 58, 72, 70, "g",
     ["Fluoride-free", "SLS-free", "Vegan"], ["Xylitol"], ["kids"], "kids, strawberry", "new", "tube", "#F8DDE0"),
    ("Mint Expanding Floss", "Waxed floss that gently expands between teeth", "Floss & Interdental", 129, 115, 64, 144, 50, "pcs",
     ["Vegan", "Cruelty-free"], ["Peppermint"], ["adults", "braces"], "floss, mint", "", "floss", "#DCEFEA"),
    ("Bamboo Interdental Brushes", "Set of 10 in mixed sizes", "Floss & Interdental", 160, 145, 82, 72, 10, "pcs",
     ["Recyclable", "BPA-free"], ["Moso Bamboo"], ["adults", "braces"], "interdental, gaps, braces", "", "floss", "#E9DCC6"),
    ("Alcohol-free Mint Mouthwash", "Fresh breath without the sting", "Mouthwash & Tongue Care", 199, 179, 108, 48, 250, "ml",
     ["SLS-free", "Paraben-free", "Vegan"], ["Peppermint", "Xylitol"], ["adults", "sensitive"], "mouthwash, rinse, fresh breath",
     "", "bottle", "#DDEFEC"),
    ("Copper Tongue Cleaner", "Pure copper, gently removes coating", "Mouthwash & Tongue Care", 249, 219, 130, 48, 1, "pcs",
     ["Ayurvedic", "Recyclable"], [], ["adults"], "tongue, copper, ayurvedic, fresh", "new", "tongue", "#F1E2CF"),
    ("Sea Salt Gum Care Rinse", "Mineral rinse for a clean, calm mouth", "Mouthwash & Tongue Care", 220, 199, 118, 48, 250, "ml",
     ["SLS-free", "Vegan"], ["Sea Salt", "Aloe Vera"], ["adults", "sensitive"], "gum care, salt", "", "bottle", "#E4ECEF"),
    ("Hotel Amenity Dental Kit", "Brush + 12 g paste in a recyclable sleeve", "Gift & Amenity Sets", 45, 39, 14, 500, 1, "pcs",
     ["Recyclable"], ["Moso Bamboo"], ["adults"], "hotel, amenity, travel, kit, bulk", "", "kit", "#EEE6DB"),
    ("Morning & Night Gift Box", "Two brushes, two pastes, floss and tongue cleaner", "Gift & Amenity Sets", 899, 799, 520, 24, 1,
     "pcs", ["Vegan", "Recyclable"], ["Neem", "Activated Charcoal"], ["adults"], "gift, set, diwali, corporate",
     "featured", "kit", "#EADCD5"),
]


def font(size):
    for name in ("georgia.ttf", "Georgia.ttf", "DejaVuSerif.ttf", "times.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_product(kind, tint, label, seed, w=1200, h=1500):
    """A calm, studio-style placeholder 'photo' so the demo looks premium without real images."""
    rnd = random.Random(seed)
    base = Image.new("RGB", (w, h), tint)
    glow = Image.new("L", (w, h), 0)
    ImageDraw.Draw(glow).ellipse((w * .1, h * .05, w * .9, h * .75), fill=150)
    base = Image.composite(Image.new("RGB", (w, h), "#FFFFFF"), base, glow.filter(ImageFilter.GaussianBlur(160)))
    d = ImageDraw.Draw(base, "RGBA")
    # soft floor shadow
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((w * .28, h * .80, w * .72, h * .86), fill=(20, 24, 31, 60))
    base.paste(shadow.filter(ImageFilter.GaussianBlur(28)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(28)))
    d = ImageDraw.Draw(base, "RGBA")
    ink = (20, 24, 31, 255)
    cx = w // 2
    if kind == "brush":
        angle_off = rnd.randint(-6, 6)
        d.rounded_rectangle((cx - 34, h * .22, cx + 34, h * .82), radius=34, fill=(196, 160, 112, 255))  # bamboo handle
        for i in range(3):
            y = h * (.42 + i * .12)
            d.line((cx - 34, y, cx + 34, y), fill=(160, 124, 80, 160), width=3)
        for i in range(-3, 4):
            d.rounded_rectangle((cx - 30 + i * 0, h * .10 + 0, cx + 30, h * .22), radius=10, fill=(30, 34, 38, 255))
        for i in range(9):
            x = cx - 26 + i * 6.5
            d.line((x, h * .10, x + angle_off * .3, h * .07), fill=(40, 44, 48, 255), width=4)
    elif kind == "tube":
        d.rounded_rectangle((cx - 170, h * .18, cx + 170, h * .74), radius=40, fill=(255, 255, 255, 255), outline=(0, 0, 0, 25), width=2)
        d.polygon([(cx - 170, h * .18), (cx + 170, h * .18), (cx + 150, h * .12), (cx - 150, h * .12)], fill=(240, 240, 238, 255))
        d.rounded_rectangle((cx - 60, h * .74, cx + 60, h * .82), radius=14, fill=(30, 34, 38, 255))
        d.rectangle((cx - 170, h * .52, cx + 170, h * .60), fill=(*bytes.fromhex(tint[1:]), 255))
    elif kind == "bottle":
        d.rounded_rectangle((cx - 150, h * .30, cx + 150, h * .80), radius=60, fill=(255, 255, 255, 235), outline=(0, 0, 0, 25), width=2)
        d.rounded_rectangle((cx - 60, h * .20, cx + 60, h * .31), radius=18, fill=(30, 34, 38, 255))
        d.rectangle((cx - 150, h * .55, cx + 150, h * .63), fill=(*bytes.fromhex(tint[1:]), 255))
    elif kind == "floss":
        d.ellipse((cx - 180, h * .30, cx + 180, h * .70), fill=(255, 255, 255, 255), outline=(0, 0, 0, 25), width=2)
        d.ellipse((cx - 60, h * .44, cx + 60, h * .56), fill=(*bytes.fromhex(tint[1:]), 255))
    elif kind == "tongue":
        bbox = (cx - 230, h * .20, cx + 230, h * .80)
        d.arc(bbox, start=200, end=340, fill=(184, 115, 51, 255), width=26)
    else:  # kit / box
        d.rounded_rectangle((cx - 260, h * .30, cx + 260, h * .78), radius=24, fill=(255, 255, 255, 255), outline=(0, 0, 0, 25), width=2)
        d.rectangle((cx - 260, h * .30, cx + 260, h * .40), fill=(*bytes.fromhex(tint[1:]), 255))
        d.line((cx, h * .30, cx, h * .78), fill=(191, 167, 122, 255), width=6)
    # droplets for freshness
    for _ in range(7):
        x, y, r = rnd.randint(80, w - 80), rnd.randint(80, int(h * .7)), rnd.randint(6, 16)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 120), outline=(255, 255, 255, 200))
    f_small, f_big = font(28), font(54)
    d.text((cx, h * .90), "P A A L V I", font=f_small, fill=ink, anchor="mm")
    d.text((cx, h * .945), label[:34], font=font(30), fill=(91, 100, 112, 255), anchor="mm")
    buf = io.BytesIO()
    base.save(buf, "WEBP", quality=82)
    return ContentFile(buf.getvalue())


def render_hero(w=2400, h=1400):
    img = Image.new("RGB", (w, h), "#EAF4F0")
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(90):
        x, y, r = random.randint(0, w), random.randint(0, h), random.randint(10, 70)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 70), outline=(255, 255, 255, 140), width=2)
    for i in range(14):
        a = i / 14 * math.pi
        d.line((w * .62 + math.cos(a) * 40, h * .2, w * .62 + math.cos(a) * 30, h * .45), fill=(30, 34, 38, 255), width=10)
    d.rounded_rectangle((w * .62 - 46, h * .44, w * .62 + 46, h * 1.2), radius=46, fill=(196, 160, 112, 255))
    img = img.filter(ImageFilter.GaussianBlur(1))
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=80)
    return ContentFile(buf.getvalue())


class Command(BaseCommand):
    help = "Load demo content (brand, products, sections) so you can see the site working."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing products/sections first.")

    def handle(self, *args, reset=False, **opts):
        if not ThemePreset.objects.exists():
            call_command("seed_themes")
        if reset:
            Product.objects.all().delete()
            Category.objects.all().delete()
            PageSection.objects.all().delete()
            HeroSlide.objects.all().delete()

        self.brand()
        self.ai()
        badges = {n: Badge.objects.update_or_create(name=n, defaults={"description": d, "order": i})[0]
                  for i, (n, d) in enumerate(BADGES)}
        ings = {n: Ingredient.objects.update_or_create(name=n, defaults={"icon": ic, "short_benefit": b, "is_spotlight": s})[0]
                for n, ic, b, s in INGREDIENTS}
        cats = {}
        for i, (name, parent, desc, icon) in enumerate(CATEGORIES):
            cats[name], _ = Category.objects.update_or_create(
                name=name, defaults={"parent": cats.get(parent), "description": desc, "icon": icon, "order": i})
        self.products(cats, badges, ings)
        self.homepage(cats)
        self.design_demo()
        self.festivals()
        clear_site_cache()
        self.stdout.write(self.style.SUCCESS("Demo content ready. Open /admin/ and the website to explore."))

    def brand(self):
        b = BrandSettings.load()
        b.tagline = "Everyday essentials, elevated."
        b.whatsapp_number = b.whatsapp_number if len(b.whatsapp_number) > 5 else "+919876543210"
        b.contact_email = "hello@paalvi.in"
        b.instagram_url = b.instagram_url or "https://instagram.com/paalvi"
        b.announcement_text = "Free shipping on orders above ₹499 · Bulk & hotel pricing on WhatsApp"
        b.announcement_link = "#catalog"
        b.announcement_active = True
        b.registered_address = "Paalvi Essentials, Pune, Maharashtra, India"
        b.manufacturer_details = "Manufactured for Paalvi Essentials, Pune, India."
        b.customer_care_details = "Customer care: hello@paalvi.in · Mon–Sat, 10am–6pm"
        b.footer_story = ("Paalvi began with a simple question: why should everyday care feel ordinary? "
                          "We make honest, beautifully simple essentials — the kind you're glad to see by your sink every morning.")
        b.save()

    def ai(self):
        c = AIAssistantConfig.load()
        c.quick_prompts = c.quick_prompts or ["Best brush for sensitive gums", "Fluoride-free options", "Build my daily routine",
                                              "Bulk pricing for my hotel", "Gift sets"]
        c.brand_knowledge = c.brand_knowledge or (
            "Paalvi makes premium, honest oral care and daily essentials in India: bamboo and recycled-handle toothbrushes, "
            "SLS-free and Ayurvedic toothpastes, floss, mouthwash and copper tongue cleaners. Clean ingredients, recyclable packs.")
        c.shipping_info = c.shipping_info or "Pan-India delivery in 3–7 working days. Free shipping above ₹499."
        c.returns_info = c.returns_info or "For hygiene reasons opened products can't be returned; damaged items are replaced free within 7 days."
        c.b2b_info = c.b2b_info or ("Wholesale for retailers, chemists, hotels, salons and corporate gifting. GST invoices, "
                                    "custom/private label from 5,000 units, hotel amenity kits with your logo.")
        c.save()

    def products(self, cats, badges, ings):
        for i, row in enumerate(PRODUCTS):
            (title, sub, cat, mrp, retail, wholesale, moq, qty, unit, b_names, i_names, suitable, tags, flags, kind, tint) = row
            sku = f"PAL-{i + 1:03d}"
            p, created = Product.objects.update_or_create(sku=sku, defaults=dict(
                title=title, subtitle=sub, category=cats[cat], mrp=Decimal(mrp), retail_price=Decimal(retail),
                wholesale_price=Decimal(wholesale), moq=moq, net_quantity=Decimal(qty), unit=unit, tags=tags,
                suitable_for=suitable, is_featured="featured" in flags, is_bestseller="bestseller" in flags,
                is_new_arrival="new" in flags, order=i,
                stock_status=Product.StockStatus.LOW if i == 4 else Product.StockStatus.IN_STOCK,
                description=(f"{sub}. Designed in India with honest materials and nothing you don't need.\n\n"
                             "Every Paalvi essential is made to feel calm and considered — from the first touch to the last use."),
                key_benefits=["Gentle on teeth and gums", "Thoughtfully minimal packaging", "Made in India"],
                how_to_use="Use twice a day, morning and night.\nBrush gently for two minutes.\nRinse and store upright to dry.",
                ingredients_text="See pack for full ingredient list." if kind in ("tube", "bottle") else "",
                shelf_life="Best before 24 months from manufacture" if kind in ("tube", "bottle") else "",
            ))
            p.badges.set([badges[n] for n in b_names])
            p.key_ingredients.set([ings[n] for n in i_names])
            if not p.images.exists():
                for j in range(2):
                    shade = tint if j == 0 else "#F3F1EC"
                    ProductImage.objects.create(product=p, order=j, alt_text=title,
                                                image=ContentFile(render_product(kind, shade, title, i * 10 + j).read(), name=f"{p.slug}-{j}.webp"))
            if kind == "brush" and not p.variants.exists():
                for k, v in enumerate(["Ultra-soft", "Soft", "Medium"] if "Kids" not in title else ["Ultra-soft"]):
                    ProductVariant.objects.create(product=p, variant_type="bristle", value=v, order=k)
                for k, (v, hx) in enumerate([("Charcoal", "#2A2D31"), ("Mint", "#8FC9B9"), ("Clay", "#E6CFC3")]):
                    ProductVariant.objects.create(product=p, variant_type="colour", value=v, swatch_hex=hx, order=10 + k)
            if kind == "tube" and not p.variants.exists():
                for k, v in enumerate(["Mint", "Herbal"] if "Kids" not in title else ["Strawberry"]):
                    ProductVariant.objects.create(product=p, variant_type="flavour", value=v, order=k)
            if not p.packages.exists():
                packs = [("Single", 1), ("Pack of 3", 3), ("Box of 12", 12), ("Carton of 144", 144)]
                if kind == "kit":
                    packs = [("Box of 24", 24), ("Hotel Amenity Kit", 100), ("Custom / Private Label", 5000)]
                for k, (n, units) in enumerate(packs):
                    PackageOption.objects.create(
                        product=p, name=n, units_per_pack=units, order=k,
                        retail_price=(Decimal(retail) * units * Decimal("0.92")).quantize(Decimal("1")) if 1 < units <= 12 else None,
                    )

    def homepage(self, cats):
        if not HeroSlide.objects.exists():
            h = HeroSlide(headline="Everyday essentials, elevated.",
                          subheadline="Soft bamboo bristles, honest pastes and calm rituals — made for India.",
                          cta_text="Explore Essentials", cta_link="#catalog")
            h.poster_image.save("hero-poster.webp", render_hero(), save=False)
            h.save()
        if PageSection.objects.exists():
            return
        S = PageSection.SectionType
        rows = [
            dict(section_type=S.FREE_FROM, title="Nothing you don't need", background_style="surface"),
            dict(section_type=S.CATEGORY_GRID, eyebrow="Shop by ritual", title="Find your essentials"),
            dict(section_type=S.FEATURED_COLLECTION, eyebrow="Loved daily", title="The Paalvi edit",
                 body="Our most-loved essentials, chosen by people who care about the small things.",
                 cta_text="See all products", cta_link="#catalog", background_style="elevated"),
            dict(section_type=S.INGREDIENT_SPOTLIGHT, eyebrow="Honest ingredients", title="Rooted in nature, refined by science",
                 body="We choose every ingredient for a reason — and we tell you what it is.", background_style="primary_tint"),
            dict(section_type=S.ROUTINE_BUILDER, eyebrow="Your ritual", title="Morning & night, simplified", items={
                "morning": [
                    {"title": "Brush", "text": "Two gentle minutes with a soft brush.", "product": "bamboo-charcoal-toothbrush"},
                    {"title": "Paste", "text": "A pea-sized amount is plenty.", "product": "neem-clove-herbal-toothpaste"},
                    {"title": "Tongue", "text": "Three soft strokes, back to front.", "product": "copper-tongue-cleaner"},
                ],
                "night": [
                    {"title": "Floss", "text": "Clean between every tooth.", "product": "mint-expanding-floss"},
                    {"title": "Brush", "text": "The most important brush of the day.", "product": "sensitive-care-ultra-soft-brush"},
                    {"title": "Rinse", "text": "Finish with an alcohol-free rinse.", "product": "alcohol-free-mint-mouthwash"},
                ]}),
            dict(section_type=S.PRODUCT_GUIDE, eyebrow="Bristle guide", title="Which brush is right for you?",
                 background_style="elevated", items=[
                    {"name": "Ultra-soft", "level": 1, "best_for": "Sensitive or receding gums",
                     "text": "Micro-fine bristles that clean with almost no pressure.", "product": "sensitive-care-ultra-soft-brush"},
                    {"name": "Soft", "level": 2, "best_for": "Most people, every day",
                     "text": "The everyday choice recommended by most dentists.", "product": "bamboo-charcoal-toothbrush"},
                    {"name": "Medium", "level": 3, "best_for": "Strong gums, light brushers",
                     "text": "A little more firmness for those who brush lightly.", "product": "recycled-grip-toothbrush"},
                 ]),
            dict(section_type=S.BRAND_STORY, eyebrow="Our story", title="Care, considered.",
                 body="Paalvi was born from a simple idea: the things you use every morning deserve as much thought as anything else "
                      "you own.\n\nWe work with Indian makers to create essentials that are gentle, honest and quietly beautiful.",
                 items=[{"stat": "0", "label": "Harsh foaming agents"}, {"stat": "100%", "label": "Recyclable outer packs"},
                        {"stat": "16", "label": "Everyday essentials"}]),
            dict(section_type=S.FOR_BUSINESS, eyebrow="Paalvi for business", title="Stock Paalvi. Gift Paalvi.",
                 body="Wholesale pricing, GST invoices and private label for businesses across India.",
                 cta_text="Get bulk pricing on WhatsApp", cta_link="whatsapp", background_style="ink", items=[
                    {"title": "Retailers", "text": "Margins that work, displays that sell.", "icon": "store"},
                    {"title": "Chemists", "text": "Dentist-trusted SKUs your customers ask for.", "icon": "pill"},
                    {"title": "Hotels", "text": "Amenity kits with your logo, from 500 units.", "icon": "hotel"},
                    {"title": "Salons & Spas", "text": "Premium touches for every guest.", "icon": "sparkles"},
                    {"title": "Corporate Gifting", "text": "Festive boxes your team will actually use.", "icon": "gift"},
                 ]),
            dict(section_type=S.TESTIMONIALS, eyebrow="Kind words", title="From people who brush with Paalvi", items=[
                {"quote": "The softest brush I've used — my gums finally stopped complaining.", "name": "Ananya", "role": "Bengaluru", "rating": 5},
                {"quote": "Our guests notice the amenity kits. That's rare for a toothbrush!", "name": "Rohan M.", "role": "Boutique hotel, Goa", "rating": 5},
                {"quote": "Neem and clove paste that doesn't taste like medicine. Love it.", "name": "Farah", "role": "Lucknow", "rating": 5},
            ]),
            dict(section_type=S.FAQ, eyebrow="Questions", title="Good to know", items=[
                {"q": "Are your toothbrushes really biodegradable?", "a": "Our bamboo handles are compostable. Bristles are nylon, so please pull them out before composting the handle."},
                {"q": "Do you offer wholesale or hotel pricing?", "a": "Yes — switch to 'Wholesale' at the top to see business prices and MOQs, or message us on WhatsApp for a quote."},
                {"q": "Is fluoride-free toothpaste right for me?", "a": "Many people prefer it, but if you're prone to cavities, ask your dentist what's best for you."},
                {"q": "How long does delivery take?", "a": "Usually 3–7 working days across India."},
            ]),
        ]
        for i, r in enumerate(rows):
            PageSection.objects.create(order=i, **r)

    def _gallery_files(self, n, seed=0):
        """Re-use the generated studio product shots as gallery photos."""
        kinds = [("brush", "#DCE9E4"), ("tube", "#E2EBD4"), ("bottle", "#DDEFEC"), ("kit", "#EADCD5"),
                 ("floss", "#DCEFEA"), ("tongue", "#F1E2CF")]
        for i in range(n):
            kind, tint = kinds[(i + seed) % len(kinds)]
            yield f"gallery-{seed}-{i}.webp", render_product(kind, tint, "Everyday essentials", 900 + seed * 10 + i)

    def design_demo(self):
        """Show off galleries, hero banners and moving text (only adds what's missing)."""
        S = PageSection.SectionType
        hero = HeroSlide.objects.order_by("order").first()
        if hero and not hero.media.exists():
            for j, (name, content) in enumerate(self._gallery_files(4)):
                m = HeroMedia(slide=hero, order=j, alt_text="Paalvi essentials")
                m.image.save(name, content, save=False)
                m.save()
        last = PageSection.objects.order_by("-order").values_list("order", flat=True).first() or 0
        spot = PageSection.objects.filter(section_type=S.INGREDIENT_SPOTLIGHT).first()
        if spot and not spot.media_shape:
            spot.media_shape = "arch"
            spot.save()
        if not PageSection.objects.filter(section_type=S.MARQUEE_TEXT).exists():
            PageSection.objects.create(section_type=S.MARQUEE_TEXT, order=last + 1, background_style="surface",
                                       items=["Soft on gums", "Kind to the earth", "Honest ingredients", "Made in India"])
        if not PageSection.objects.filter(section_type=S.HERO_BANNER).exists():
            sec = PageSection.objects.create(
                section_type=S.HERO_BANNER, order=last + 2, hero_layout="orbit", background_style="primary_tint",
                eyebrow="The ritual collection", title="Small things, done beautifully.",
                body="Every brush, paste and rinse is designed to feel calm in your hand — and kind to the planet.",
                cta_text="Shop the ritual", cta_link="#catalog", media_shape="circle", decor_shape="rings",
                text_animation="blur_words", pointer_effect="parallax")
            for j, (name, content) in enumerate(self._gallery_files(6, seed=3)):
                m = SectionMedia(section=sec, order=j, alt_text="Paalvi essentials")
                m.image.save(name, content, save=False)
                m.save()
        created_gallery = not PageSection.objects.filter(section_type=S.GALLERY).exists()
        if created_gallery:
            sec = PageSection.objects.create(
                section_type=S.GALLERY, order=last + 3, eyebrow="In the studio", title="Made to be looked at",
                gallery_style="coverflow", media_shape="arch", hover_effect="tilt_3d", entrance_animation="zoom_in",
                divider_shape="wave", background_style="elevated")
            for j, (name, content) in enumerate(self._gallery_files(6, seed=1)):
                m = SectionMedia(section=sec, order=j, alt_text="Paalvi essentials",
                                 caption=["Bamboo brush", "Herbal paste", "Fresh rinse", "Gift box", "Floss", "Copper cleaner"][j])
                m.image.save(name, content, save=False)
                m.save()
            # Weave the new blocks into a pleasant page flow.
            flow = [S.FREE_FROM, S.CATEGORY_GRID, S.FEATURED_COLLECTION, S.INGREDIENT_SPOTLIGHT, S.HERO_BANNER,
                    S.ROUTINE_BUILDER, S.MARQUEE_TEXT, S.PRODUCT_GUIDE, S.GALLERY, S.BRAND_STORY, S.FOR_BUSINESS,
                    S.TESTIMONIALS, S.FAQ]
            rank = {t: i for i, t in enumerate(flow)}
            for i, sec in enumerate(sorted(PageSection.objects.all(), key=lambda x: (rank.get(x.section_type, 99), x.order))):
                PageSection.objects.filter(pk=sec.pk).update(order=i)

    def festivals(self):
        at = ActiveTheme.load()
        if at.festivals.exists():
            return
        dates = [
            ("Christmas 2026", "Christmas Velvet & Frost", date(2026, 12, 20), date(2026, 12, 27)),
            ("New Year 2027", "New Year Champagne", date(2026, 12, 30), date(2027, 1, 2)),
            ("Pongal / Sankranti 2027", "Pongal / Sankranti Harvest", date(2027, 1, 13), date(2027, 1, 16)),
            ("Holi 2027 (check date)", "Holi Prism", date(2027, 3, 20), date(2027, 3, 23)),
            ("Independence Day 2027", "Independence Tricolor Luxe", date(2027, 8, 13), date(2027, 8, 16)),
            ("Diwali 2027 (check date)", "Diwali Royal Gold", date(2027, 10, 25), date(2027, 11, 1)),
        ]
        for label, preset, start, end in dates:
            FestivalSchedule.objects.create(active_theme=at, label=label, preset=ThemePreset.objects.get(name=preset),
                                            start_date=start, end_date=end)
