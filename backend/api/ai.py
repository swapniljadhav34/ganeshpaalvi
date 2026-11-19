"""
Paalvi Care Guide — scalable RAG (retrieval-augmented generation).

Instead of sending the whole catalog to the AI (impossible at 50,000 products), we:
  1. read the visitor's message for concerns, buyer type and budget,
  2. fetch only the ~8 best-matching live products from the database,
  3. give the AI just those products + the owner's brand knowledge,
  4. return the AI's reply AND structured product cards the website can show.

Works with any OpenAI-compatible provider (Groq by default, Gemini, Ollama…).
"""

import logging
import re

from django.conf import settings
from django.db.models import Q

from catalog.models import Product
from storefront.models import AIAssistantConfig, BrandSettings

from .serializers import product_card

log = logging.getLogger("paalvi")

# Visitor words → what to look for in product data.
CONCERNS = {
    "sensitive": {"words": ["sensitive", "sensitivity", "gum", "gums", "gentle", "soft", "receding"],
                  "suitable": ["sensitive"], "terms": ["sensitive", "soft", "gentle"]},
    "whitening": {"words": ["white", "whiten", "whitening", "stain", "stains", "yellow", "coffee", "tea"],
                  "terms": ["whitening", "charcoal", "stain"]},
    "kids": {"words": ["kid", "kids", "child", "children", "baby", "toddler", "son", "daughter"],
             "suitable": ["kids"], "terms": ["kids"]},
    "braces": {"words": ["braces", "aligner", "aligners", "orthodontic"], "suitable": ["braces"], "terms": ["braces", "orthodontic"]},
    "fluoride_free": {"words": ["fluoride-free", "fluoride free", "no fluoride", "without fluoride"], "badges": ["fluoride-free"]},
    "vegan": {"words": ["vegan", "cruelty", "plant"], "badges": ["vegan", "cruelty-free"]},
    "ayurvedic": {"words": ["ayurveda", "ayurvedic", "herbal", "neem", "clove", "natural"], "badges": ["ayurvedic"],
                  "terms": ["herbal", "neem", "clove", "ayurvedic"]},
    "eco": {"words": ["eco", "bamboo", "plastic", "sustainable", "biodegradable", "recyclable"], "badges": ["recyclable"],
            "terms": ["bamboo", "eco"]},
    "fresh_breath": {"words": ["breath", "bad breath", "fresh", "mouthwash", "tongue"], "terms": ["fresh", "mouthwash", "tongue", "mint"]},
    "floss": {"words": ["floss", "flossing", "interdental"], "terms": ["floss"]},
    "travel": {"words": ["travel", "trip", "kit"], "terms": ["travel", "kit"]},
    "gift": {"words": ["gift", "gifting", "hamper", "diwali gift"], "terms": ["gift", "set", "kit"]},
}
BUYER_WORDS = {
    "hotel": ["hotel", "resort", "homestay", "airbnb", "amenity", "amenities", "guest"],
    "retailer": ["shop", "store", "retailer", "kirana", "supermarket", "resell"],
    "chemist": ["chemist", "pharmacy", "medical store", "druggist"],
    "salon": ["salon", "spa", "parlour", "parlor"],
    "corporate": ["corporate", "employees", "office", "company gift", "bulk gift"],
    "distributor": ["distributor", "distribution", "dealer", "wholesaler", "stockist"],
}
DENTIST_WORDS = ["pain", "painful", "bleeding", "bleed", "blood", "swelling", "swollen", "abscess", "toothache",
                 "throbbing", "pus", "loose tooth", "persistent", "cavity", "infection"]
STOP = set("i me my we our you your a an the and or for to of in on with is are be it this that what which best good "
           "need want some any have has please suggest recommend show tell about can do does".split())

TONES = {
    "warm": "Warm, caring and friendly — like a thoughtful friend who knows oral care.",
    "clinical": "Clear, calm and precise — like a knowledgeable pharmacist. No fluff.",
    "playful": "Light, upbeat and a little playful — but always respectful and clear.",
}


def analyse(message: str):
    """Pull concerns, buyer type, budget and keywords out of a visitor's message."""
    text = message.lower()
    concerns = [k for k, c in CONCERNS.items() if any(w in text for w in c["words"])]
    buyer = next((b for b, words in BUYER_WORDS.items() if any(w in text for w in words)), None)
    if not buyer and re.search(r"\b(bulk|wholesale|moq|cartons?|b2b|gst invoice)\b", text):
        buyer = "retailer"
    budget = None
    m = re.search(r"(?:under|below|less than|upto|up to|within|budget|₹|rs\.?|inr)\s*₹?\s*(\d{2,6})", text)
    if m:
        budget = int(m.group(1))
    keywords = [w for w in re.findall(r"[a-z][a-z\-]{2,}", text) if w not in STOP][:8]
    dentist = any(w in text for w in DENTIST_WORDS)
    return {"concerns": concerns, "buyer": buyer, "budget": budget, "keywords": keywords, "dentist": dentist}


def retrieve(intent, limit=8):
    """Fetch the most relevant live products. Score in Python over a small candidate pool."""
    base = Product.objects.live()
    cond = Q()
    badges, suitable, terms = set(), set(), set(intent["keywords"])
    for c in intent["concerns"]:
        spec = CONCERNS[c]
        badges |= set(spec.get("badges", []))
        suitable |= set(spec.get("suitable", []))
        terms |= set(spec.get("terms", []))
    for b in badges:
        cond |= Q(badges__slug=b)
    for s in suitable:
        cond |= Q(suitable_for__icontains=f'"{s}"')
    for t in terms:
        cond |= Q(title__icontains=t) | Q(tags__icontains=t) | Q(subtitle__icontains=t) | Q(category__name__icontains=t)
    if intent["buyer"]:
        base = base.filter(wholesale_price__isnull=False) if base.filter(wholesale_price__isnull=False).exists() else base
    if intent["budget"]:
        base = base.filter(retail_price__lte=intent["budget"])

    pool = list(base.filter(cond).distinct().for_cards()[:60]) if cond else []

    def score(p):
        s = 0
        hay = f"{p.title} {p.subtitle} {p.tags} {p.category.name}".lower()
        s += sum(3 for b in p.badges.all() if b.slug in badges)
        s += sum(3 for x in (p.suitable_for or []) if x in suitable)
        s += sum(1 for t in terms if t in hay)
        s += 1 if p.is_bestseller else 0
        return s

    pool.sort(key=score, reverse=True)
    chosen = pool[:limit]
    if len(chosen) < 3:  # fallback: featured & bestsellers so the guide always has something real to suggest
        extra = base.exclude(pk__in=[p.pk for p in chosen]).filter(Q(is_featured=True) | Q(is_bestseller=True)).for_cards()
        chosen += list(extra.order_by("order", "-created_at")[: limit - len(chosen)])
    return chosen


def product_context(products):
    lines = []
    for p in products:
        badges = ", ".join(b.name for b in p.badges.all()) or "—"
        variants = "; ".join(f"{v.get_variant_type_display()}: {v.value}" for v in p.variants.all()) or "—"
        packs = "; ".join(
            f"{pk.name} ({pk.units_per_pack} pcs"
            + (f", retail ₹{pk.retail_price:.0f}" if pk.retail_price else "")
            + (f", wholesale ₹{pk.wholesale_price:.0f}" if pk.wholesale_price else "")
            + (f", MOQ {pk.moq} packs" if pk.moq else "") + ")"
            for pk in p.packages.all()
        ) or "—"
        wholesale = f"₹{p.wholesale_price:.0f}/pc, MOQ {p.moq} pcs" if p.wholesale_price else "not offered"
        lines.append(
            f"- [{p.slug}] {p.title} — {p.subtitle}\n"
            f"  Category: {p.category.name} | MRP ₹{p.mrp:.0f} | Retail ₹{p.retail_price:.0f} | Wholesale {wholesale}\n"
            f"  Badges: {badges} | Suitable for: {', '.join(p.suitable_for or []) or '—'} | Stock: {p.get_stock_status_display()}\n"
            f"  Variants: {variants} | Packs: {packs}\n"
            f"  Benefits (as stated by Paalvi): {' / '.join(p.key_benefits or []) or '—'}"
        )
    return "\n".join(lines) or "(no matching products)"


def build_messages(cfg: AIAssistantConfig, brand: BrandSettings, message, history, products, intent, tier):
    system = f"""You are "{cfg.assistant_name}", the shopping guide for {brand.brand_name} — premium toothbrushes, toothpaste,
oral care and daily essentials in India. Tone: {TONES.get(cfg.tone, TONES['warm'])}

STRICT RULES:
1. Recommend ONLY products listed under PRODUCTS below. Never invent products, prices, discounts, ingredients, stock or claims.
2. Quote prices in Indian Rupees exactly as given (₹, incl. all taxes). If something isn't in the data, say you'll check and suggest WhatsApp.
3. Describe benefits ONLY as stated in the product data. No medical diagnosis, no cure/treatment claims.
4. If the visitor mentions pain, bleeding gums, swelling, a loose tooth or sensitivity that has lasted a while, gently suggest seeing a dentist first, then offer gentle products.
5. For bulk/business buyers, mention wholesale price per piece, MOQ and suitable pack sizes; invite them to WhatsApp for a quote.
6. Keep replies short for mobile: 2–5 sentences or a few bullets. Mention products by name. Use Indian English.
7. When you recommend a product, include its code in square brackets exactly once, like [bamboo-brush-soft], so the website can show its card.

BRAND KNOWLEDGE:
{cfg.brand_knowledge or '—'}
SHIPPING: {cfg.shipping_info or 'Ask the team on WhatsApp.'}
RETURNS: {cfg.returns_info or 'Ask the team on WhatsApp.'}
BUSINESS / WHOLESALE: {cfg.b2b_info or 'Wholesale pricing and MOQs are shown per product. Custom quotes on WhatsApp.'}

VISITOR CONTEXT: viewing {tier} prices; detected buyer type: {intent['buyer'] or 'shopper'};
concerns: {', '.join(intent['concerns']) or 'none detected'}; budget: {('₹' + str(intent['budget'])) if intent['budget'] else 'not stated'}.
{'IMPORTANT: The visitor mentioned symptoms — start by kindly recommending a dentist visit.' if intent['dentist'] else ''}

PRODUCTS (the only ones you may mention):
{product_context(products)}"""
    msgs = [{"role": "system", "content": system}]
    for turn in (history or [])[-6:]:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        content = str(turn.get("content", ""))[:800]
        if content:
            msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": message[:1000]})
    return msgs


def fallback_reply(products, intent, brand):
    """Used when the AI provider is down or not configured — still genuinely helpful."""
    parts = []
    if intent["dentist"]:
        parts.append("Since you mentioned discomfort, it's best to see a dentist first — they can check what's going on.")
    if products:
        names = ", ".join(p.title for p in products[:3])
        parts.append(f"Here are a few Paalvi essentials that may suit you: {names}. Tap a card to see details.")
    else:
        parts.append("I couldn't find a close match just now.")
    parts.append("For personal advice or bulk pricing, our team is happy to help on WhatsApp.")
    return " ".join(parts)


_client = None


def ai_client():
    """One shared client (connection pooling); no retries so a slow provider can't hold a worker for long."""
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(base_url=settings.AI_BASE_URL, api_key=settings.AI_API_KEY or "ollama",
                         timeout=settings.AI_TIMEOUT_SECONDS, max_retries=0)
    return _client


def sign_reply(text):
    """Signature for an assistant reply, so the browser can't invent earlier 'assistant' turns."""
    from django.core.signing import Signer

    return Signer(salt="paalvi-guide").signature((text or "")[:2000])


def ask_guide(request, message, history=None, tier="retail"):
    cfg = AIAssistantConfig.load()
    brand = BrandSettings.load()
    intent = analyse(message)
    products = retrieve(intent)
    reply, ai_ok = None, False

    if settings.AI_API_KEY or "localhost" in settings.AI_BASE_URL or "127.0.0.1" in settings.AI_BASE_URL:
        try:
            resp = ai_client().chat.completions.create(
                model=settings.AI_MODEL,
                messages=build_messages(cfg, brand, message, history, products, intent, tier),
                temperature=0.4,
                max_tokens=450,
            )
            reply = (resp.choices[0].message.content or "").strip()
            ai_ok = bool(reply)
        except Exception as exc:  # timeouts, quota, network — never break the website
            log.warning("AI guide failed: %s", exc)

    if not reply:
        reply = fallback_reply(products, intent, brand)

    # Show cards for products the AI actually mentioned first, then the rest of the retrieved set.
    mentioned = re.findall(r"\[([a-z0-9\-]+)\]", reply)
    by_slug = {p.slug: p for p in products}
    ordered = [by_slug[s] for s in dict.fromkeys(mentioned) if s in by_slug]
    ordered += [p for p in products if p not in ordered]
    clean_reply = re.sub(r"\s*\[([a-z0-9\-]+)\]", lambda m: "" if m.group(1) in by_slug else m.group(0), reply)

    return {
        "reply": clean_reply,
        "products": [product_card(request, p) for p in ordered[:4 if mentioned else 3]],
        "suggest_dentist": intent["dentist"],
        "buyer_type": intent["buyer"],
        "ai": ai_ok,
    }
