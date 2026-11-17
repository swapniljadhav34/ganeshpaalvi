# Paalvi — paalvi.in

A premium, mobile-first brand showroom and retail + wholesale catalog for oral care and daily essentials.

- **backend/**: Django 5 + Django Ninja API + Unfold admin ("Paalvi Studio")
- **frontend/**: React 18 + Vite, Framer Motion, TanStack Query
- **BRIEF.md**: brand and design brief

Everything visitors see comes from the admin: text, photos, videos, prices, themes and homepage sections.

---

## Run it on your computer

You need Python 3.12+ and Node 20+.

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # Mac/Linux: cp .env.example .env
python manage.py migrate
python manage.py seed_themes    # 24 theme presets
python manage.py seed_demo      # optional: demo products, sections & photos
python manage.py createsuperuser
python manage.py runserver      # http://127.0.0.1:8000/admin/

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

In development, Vite forwards `/api` and `/media` to Django, so there's nothing else to configure.

## Owner guide (Paalvi Studio, `/admin/`)

| Sidebar tab | What you do there |
|---|---|
| **Dashboard** | Live products, low stock, new leads, top-enquired products, B2B vs shopper split, live theme, quick buttons |
| **Brand & Contact** | Name, logos, WhatsApp number (powers every WhatsApp button), socials, GSTIN, address, announcement bar, footer, Google/share defaults |
| **Theme & Festival Studio** | Pick your everyday theme, schedule festivals by date, or click **Use this theme now** on any preset. Colour pickers show a live preview and a readability check |
| **Site Design Studio** | The look and motion of the whole site: default shape, entrance, text and hover animations, mouse effects, decorative shapes, section edge shapes, speed, custom cursor, loading screen, button shape/hover; header style, scroll behaviour, wordmark size and spacing; footer style plus the big footer word (text, size, 9 animations); product card style, image shape and proportions. **Header menu links** and **Footer columns & links** (including extra emails and phone numbers) are fully editable |
| **Homepage Builder** | Hero slides in **24 layouts**, with rotating extra photos/videos, and page sections (now including *Animated Hero Banner*, *Media Gallery* and *Big Moving Text*). Every slide and section has a **Shape & animation** tab (23 shapes, 18 entrances, 14 text animations, 10 hover effects, 9 media motions, 12 gallery styles, 5 mouse effects, 11 decor shapes, 9 edge shapes). A floating **Live preview** shows the real site on phone, tablet or computer and updates as you type. Drag-to-reorder and show-from/until dates as before |
| **Products** | Products with drag-to-reorder photos (big phone photos are auto-converted to WebP), variants, pack sizes, ingredients and badges. Bulk actions: show/hide, featured, discount %, move category, stock status. **Download Excel template**, then Import/Export |
| **Leads & Enquiries** | Every WhatsApp tap, form, AI hand-off and B2B request. Move them New → Contacted → Quoted → Won/Lost, chat on WhatsApp, export to Excel |
| **AI Concierge** | Assistant name, greeting, suggestion chips, tone, and what it knows (brand, shipping, returns, wholesale terms) |

Excel import: fill the **Products** sheet first (one row per SKU; re-uploading the same SKU updates it), then **Variants** and **Packs** from their own admin pages.

Where the catalog appears on the homepage: right after the "Featured Collection" section (or the first "Category Grid" if there's no featured section).

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/bootstrap` | Brand, live theme, hero, sections, categories, badges, AI config. Cached 5 min and cleared automatically on every admin save |
| `GET /api/products` | 24 per page. Filters: `q, category, badge, suitable_for, variant (bristle:soft), sort, min_discount, min_price, max_price, featured, tier, page` |
| `GET /api/products/{slug}` | Full detail + related + "complete your routine" |
| `POST /api/ai-guide` | RAG over the catalog (top 8 matching products only), with safety rules. 15/min per IP |
| `POST /api/inquiry` | Lead capture with a honeypot. 5/min per IP |
| `/sitemap.xml`, `/robots.txt` | Generated automatically |

Interactive API docs: `/api/docs` (only while `DJANGO_DEBUG=true`).

## WhatsApp message format

```
Hi Paalvi 👋 I'd like to enquire about:
🪥 Bamboo Charcoal Toothbrush
SKU: PAL-001 · Bristle: Soft · Colour: Mint
Pack: Carton of 144 × 2
Price seen: ₹72/pc (Wholesale) · MOQ 144
Est. total: ₹20,736
I'm a: Hotel · Pune
🔗 https://paalvi.in/p/bamboo-charcoal-toothbrush
```

## AI Care Guide

The guide works with any OpenAI-compatible provider: set `AI_BASE_URL`, `AI_API_KEY` and `AI_MODEL` in `backend/.env`. The default is Groq `llama-3.1-8b-instant` (free tier). Gemini and Ollama examples are in `.env.example`.

Without a key, or if the provider is down, the guide still answers. It falls back to a helpful reply that suggests real matching products. It never invents products or prices, makes no medical claims, and suggests a dentist when a visitor mentions pain, bleeding or swelling.

## Deploying to production

**Option A — one server (simplest).** Django serves the API, the admin and the built React app.
```bash
cd frontend && npm ci && npm run build          # creates frontend/dist
cd ../backend
# .env: DJANGO_DEBUG=false, DJANGO_SECRET_KEY=..., DATABASE_URL=postgres://..., SITE_URL=https://paalvi.in
python manage.py migrate && python manage.py collectstatic --noinput
gunicorn config.wsgi --workers 3 --timeout 60
```
`/p/<slug>` is rendered by Django with real Open Graph tags (product photo, name, ₹ price), so WhatsApp and Facebook previews look right even though the site is a React app. If your media lives on disk, have your web server (e.g. nginx) serve `/media/`, or turn on R2 (below).

**Option B — split hosting.** Put the frontend on a static host (Vercel, Netlify, Cloudflare Pages) with `VITE_API_URL=https://api.paalvi.in`, and the backend on Render, Railway or a VPS. To keep share previews working, route `/p/*`, `/sitemap.xml` and `/robots.txt` to Django (a rewrite on the static host), and add an SPA fallback to `index.html` for everything else.

**Production checklist**
- PostgreSQL (`DATABASE_URL`). Migration `catalog.0002` enables `pg_trgm` for fast, typo-tolerant search.
- Optional `REDIS_URL`. Without it, a file cache in `backend/.cache` is used; it is shared by all workers on one server.
- Optional Cloudflare R2 for photos and videos: `USE_S3_MEDIA=true` plus the `S3_*` variables.
- `LEAD_NOTIFY_EMAILS` + SMTP settings for new-lead emails.
- CORS is locked to `https://paalvi.in` and `https://www.paalvi.in` (localhost is added only in debug).

## Performance notes

- Catalog cards carry only what a card shows. List pages avoid a COUNT after page 1 and use composite indexes. Once 200+ cards are loaded, the grid switches to windowed rendering.
- Images are auto-converted to WebP, with 480px and 960px thumbnails generated on save.
- On low-end phones (≤4 CPU cores, ≤4 GB RAM, Save-Data or 2G) the hero video, ambient particles, glass blur and smooth scrolling all switch off automatically. Reduced-motion is respected everywhere.
- The AI drawer is lazy-loaded; fonts for festival themes load only when that theme is live.
