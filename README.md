# Paalvi — paalvi.in

A premium, mobile-first brand showroom and retail + wholesale catalog for oral care and daily essentials.

- **backend/**: Django 5 + Django Ninja API + Unfold admin (site settings) + `ops` app (inventory, production, accounting, analytics, staff roles)
- **frontend/**: React 18 + Vite storefront, plus **Paalvi Studio** at `/studio` (role-based staff app, loaded only for staff)
- **BRIEF.md**: brand and design brief · **DEPLOY.md**: going live on Oracle, AWS, Hostinger, Docker or Heroku

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
echo DJANGO_DEBUG=true> .env    # development mode (production is the default and needs a secret key)
python manage.py migrate
python manage.py seed_themes    # 24 theme presets
python manage.py seed_demo      # optional: demo products, sections & photos
python manage.py seed_ops       # optional: demo stock, batches, invoices, traffic, 3D models (--staff adds demo employees)
python manage.py createsuperuser
python manage.py test           # 27 tests
python manage.py runserver      # http://127.0.0.1:8000/admin/

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

In development, Vite forwards `/api` and `/media` to Django, so there's nothing else to configure.

## Owner guide (site admin, `/admin/` — or your private ADMIN_URL)

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
| `POST /api/analytics/track` | Cookie-free page-view beacon (no IPs stored) |
| `/api/staff/...` | Paalvi Studio API: session login + CSRF, role permissions on every endpoint |
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

## Paalvi Studio (`/studio`) — for the team

Staff sign in at **`/studio`**. Each role sees only its own tabs, and the server checks every request (hiding a tab is never the security).

| Role | Tabs |
|---|---|
| Super admin (owner) | Everything + Team & settings + the site admin |
| Accountant | Accounting |
| Inventory manager | Inventory (adjust, batches/expiry), Production (view) |
| Production manager | Production (create, assign, any batch), Inventory (view) |
| Operations employee | Inventory (adjust), Production (their assigned batches), Orders & enquiries |
| Catalog & media employee | Catalog & 3D, Inventory (view) |
| Wholesale manager | Orders & enquiries, Inventory (view) |

- **Inventory**: stock per SKU (product or variant) with reserved/available, batch & expiry, quick ± adjustments (reason required). Every change runs in a locked database transaction and is written to a permanent movement log. Alerts raise and clear themselves: *Out of stock*, *Low stock*, *Expiring soon*, *Production needed*. The website's stock label follows real stock. Owner-only: movement log, alert levels, settings, CSV export.
- **Production**: Kanban from *Planned* to *Completed*. Completing a batch adds its good pieces to stock exactly once and clears flags. Batches can be planned straight from a flagged item.
- **Accounting** (owner + accountant only): GST invoices (CGST/SGST or IGST, gap-free numbers per financial year), payments (UPI/bank/cash/card, no overpaying), expenses with **private** receipts, revenue vs expenses, receivables, GST payable estimate, CSV exports.
- **Traffic** (owner): cookie-free visit counts, unique sessions, top products, mobile vs desktop, retail vs wholesale, daily trend.
- **Catalog & 3D**: upload `.glb` models and posters, choose which products spin in the homepage **3D showcase** hero (hero layout #25, also usable as an Animated Hero Banner section).
- **Team**: add staff with a role (one-time password), change roles, block access, reset passwords.

## Deploying

See **[DEPLOY.md](DEPLOY.md)** — Oracle Cloud (free), AWS, Hostinger VPS, any Docker host, or Heroku/Render — plus the production checklist.

## Performance notes

- Catalog cards carry only what a card shows. List pages avoid a COUNT after page 1 and use composite indexes. Once 200+ cards are loaded, the grid switches to windowed rendering.
- Images are auto-converted to WebP, with 480px and 960px thumbnails generated on save.
- On low-end phones (≤4 CPU cores, ≤4 GB RAM, Save-Data or 2G) the hero video, ambient particles, glass blur and smooth scrolling all switch off automatically. Reduced-motion is respected everywhere.
- The AI drawer is lazy-loaded; fonts for festival themes load only when that theme is live.
