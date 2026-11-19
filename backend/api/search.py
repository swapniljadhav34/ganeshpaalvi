"""
Product search & filtering — shared by the catalog API and the AI guide.
Uses PostgreSQL trigram fuzzy matching when available, plain 'contains' on SQLite.
"""

from django.db.models import Exists, OuterRef, Q

from catalog.models import Category, Product, ProductVariant, is_postgres

# Each list value adds a join/subquery, so never accept more than a handful from visitors.
MAX_LIST = 5

SORTS = {
    "newest": ["-created_at"],
    "price_asc": ["retail_price", "-created_at"],
    "price_desc": ["-retail_price", "-created_at"],
    "discount": ["-discount_percent", "-created_at"],
    "bestseller": ["-is_bestseller", "-is_featured", "order", "-created_at"],
    "featured": ["-is_featured", "order", "-created_at"],
}


def text_search(qs, q):
    """Search title, subtitle, tags and SKU; on PostgreSQL fall back to fuzzy matches for typos."""
    q = (q or "").strip()[:80]
    if not q:
        return qs
    words = [w for w in q.split() if len(w) > 1][:6] or [q]
    cond = Q()
    for w in words:
        cond &= Q(title__icontains=w) | Q(subtitle__icontains=w) | Q(tags__icontains=w) | Q(category__name__icontains=w)
    exact = qs.filter(cond | Q(sku__iexact=q) | Q(ean=q))
    if is_postgres() and not exact.exists():
        from django.contrib.postgres.search import TrigramSimilarity

        return (
            qs.annotate(sim=TrigramSimilarity("title", q))
            .filter(Q(sim__gt=0.18) | Q(tags__trigram_similar=q))
            .order_by("-sim")
        )
    return exact


def filter_products(qs, *, q=None, category=None, badge=None, suitable_for=None, variant=None, min_discount=None,
                    featured=None, tier=None, min_price=None, max_price=None, sort=None):
    if category:
        cat = Category.objects.filter(slug=category, is_active=True).first()
        qs = qs.filter(category_id__in=cat.descendant_ids()) if cat else qs.none()
    for slug in [b for b in (badge or "").split(",") if b][:MAX_LIST]:
        qs = qs.filter(badges__slug=slug.strip())
    for who in [s for s in (suitable_for or "").split(",") if s][:MAX_LIST]:
        qs = qs.filter(suitable_for__icontains=f'"{who.strip()}"')
    # variant=bristle:soft,flavour:mint  (also accepts bristle=soft)
    for pair in [v for v in (variant or "").split(",") if v][:MAX_LIST]:
        sep = ":" if ":" in pair else "="
        if sep not in pair:
            continue
        vtype, value = (x.strip() for x in pair.split(sep, 1))
        qs = qs.filter(Exists(ProductVariant.objects.filter(product=OuterRef("pk"), variant_type=vtype, value__iexact=value)))
    if min_discount:
        qs = qs.filter(discount_percent__gte=min_discount)
    if featured:
        qs = qs.filter(is_featured=True)
    if tier == "wholesale":
        qs = qs.filter(wholesale_price__isnull=False)
    if min_price is not None:
        qs = qs.filter(retail_price__gte=min_price)
    if max_price is not None:
        qs = qs.filter(retail_price__lte=max_price)
    was_fuzzy = False
    if q:
        before = qs
        qs = text_search(qs, q)
        was_fuzzy = qs.query.order_by != before.query.order_by
    if not was_fuzzy or sort:
        qs = qs.order_by(*SORTS.get(sort or "featured", SORTS["featured"]), "pk")
    return qs
