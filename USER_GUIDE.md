# Paalvi — User Guide

This guide is for the store owner and team. It covers running the app on your computer, managing your shop, and putting the website online.

---

## 1. What's inside

| Part | Address (on your computer) | Who uses it | What it's for |
|---|---|---|---|
| **Website** | http://127.0.0.1:8000/ | Customers | Your showroom: products, photos, WhatsApp enquiries |
| **Designer** | http://127.0.0.1:8000/admin/ | Owner, designers | Change everything customers see: brand, products, photos, homepage, theme |
| **Studio** | http://127.0.0.1:8000/studio | Owner and staff | Orders, stock, production, accounts, team |

Everything on the website comes from the Designer. You never need to edit code.

---

## 2. Start the app on your computer

**You need (one time):** [Python 3.12+](https://www.python.org/downloads/) (tick *"Add Python to PATH"* while installing) and [Node.js 20+](https://nodejs.org/).

1. Open the Paalvi folder.
2. **Double-click `START_PAALVI.bat`.**
3. **First time only:** setup takes a few minutes. You'll be asked to create the **owner login** (username, email, password). Keep it safe.
4. Your browser opens the website. **Keep the black window open** while you work. Closing it stops the app.

Next time, just double-click `START_PAALVI.bat` again. All your products and settings are saved.

---

## 3. Sign in

- **Designer:** open http://127.0.0.1:8000/admin/ and sign in with the owner login.
- **Studio:** open http://127.0.0.1:8000/studio and use the same login. Staff use the logins you create for them (see section 5).

---

## 4. Everyday tasks in the Designer

The left sidebar groups everything. The **Dashboard** shows live products, low stock, new enquiries and quick buttons.

### Set up your brand (do this first)
**Brand & Contact → Brand & contact details.** Fill in the brand name, logos, **WhatsApp number**, email, phone, address, GSTIN and social links.
> The WhatsApp number powers every WhatsApp button on the website. Include the country code, e.g. `919876543210`.

### Add or edit a product
1. **Products → Products → Add product**.
2. Fill in the title, category, description, benefits and how to use.
3. Add **photos**. Drag to reorder; the first photo is the main one. Phone photos are resized automatically.
4. Optional: variants (colour, bristle, flavour), pack sizes, ingredients and badges (vegan, fluoride-free…).
5. Tick **Active** to show it on the website, then **Save**.

**Many products at once:** on the Products page, click **Download Excel template**, fill it in, then use **Import**. Re-importing the same SKU updates that product.

**Hide a product:** untick **Active**, or select several products and choose the bulk action.

### Change the homepage
- **Homepage Builder → Hero slides:** the big banner at the top. Choose a layout, add photos or videos, and set show-from/until dates.
- **Homepage Builder → Page sections:** the blocks below the banner (featured products, categories, gallery, text). Drag to change the order.
- A floating **Live preview** shows the real site on phone, tablet or computer as you type.

### Change the look
- **Theme & Festival Studio → Active theme & schedule:** pick your everyday colours, or schedule a festival theme by date (Diwali, Holi…).
- **Site Design Studio:** animations, header and footer style, product card style, header menu links and footer links.
- **Site Design Studio → Translations:** edit website words in Indian languages.

### Reply to enquiries
**Leads & Enquiries → All enquiries** lists every WhatsApp tap and enquiry form. Move each one through **New → Contacted → Quoted → Won/Lost**. You can export the list to Excel.

---

## 5. Studio — for your team

Open http://127.0.0.1:8000/studio. Each person sees only the tabs their role allows.

| Tab | What it does |
|---|---|
| **Orders & enquiries** | Create orders, move them Pending → Confirmed → Packed → In transit → Delivered, and print receipts |
| **Inventory** | Stock per product, quick ± adjustments (a reason is required), batches and expiry dates. Alerts for low stock or expiry appear automatically |
| **Production** | Plan and track production batches. Finished batches are added to stock |
| **Accounting** | GST invoices, payments, expenses with receipts, and reports (owner and accountant only) |
| **Traffic** | Website visits and top products (owner) |
| **Team & roles** | Add staff, choose their role and reset passwords (owner only) |

**Add a staff member:** Studio → **Team & roles** → add person → choose a role (e.g. *Inventory manager*, *Accountant*, *Designer*). They get a one-time password to sign in.

---

## 6. Put the website online (Hostinger shared hosting)

Hostinger **shared/web hosting** can't run the full app, but it can host a **static copy** of your website. It has all products and photos, **without prices**, and enquiries go to WhatsApp.

### Build the static website: one click
Use **either** option:
- **Designer → Dashboard →** card **"Static website · no prices"** → type your website address (e.g. `https://paalvi.in`) → **📦 Build & download**. You get `paalvi-static-website.zip`.
- **Or** double-click **`BUILD_STATIC_SITE.bat`** in the Paalvi folder, type your website address and press Enter. It creates the `static_site` folder and `static_site.zip`.

It takes about a minute. Keep `START_PAALVI.bat` running if you use the Dashboard button.

### Upload to Hostinger
1. Log in to **Hostinger → Websites → Manage → File Manager**.
2. Open the **`public_html`** folder. Delete the old files there (keep a backup if you're unsure).
3. **Upload** the ZIP file, right-click it → **Extract** into `public_html`, then delete the ZIP.
4. Open your website address. Done.

> Hidden files must be included. The ZIP contains `.htaccess`, which makes product links like `/p/toothpaste` work. Extracting the ZIP in File Manager keeps it.

### Update the online website
Whenever you change products, photos or the homepage in the Designer, build again and repeat the upload. The online site does **not** update by itself.

### What's different on the static website
| Feature | Full app (your computer / VPS) | Static website (Hostinger shared) |
|---|---|---|
| Products, photos, search, filters | ✅ | ✅ |
| Prices, MRP, wholesale prices | ✅ | ❌ hidden: "Ask us for price & availability" |
| WhatsApp buttons | ✅ (logged as enquiries) | ✅ (straight to WhatsApp, not logged) |
| Enquiry form | Saved in **Leads & Enquiries** | Opens WhatsApp with the details filled in |
| AI Care Guide, order tracking, visit counts | ✅ | ❌ |
| Designer and Studio | ✅ | ❌ use them on your computer |

**Want the full app online (prices, enquiries saved, Studio for staff)?** That needs a server that can run it, such as a Hostinger **VPS**, AWS Lightsail or Oracle Cloud (free). See `DEPLOY.md`.

---

## 7. Backups

Your shop's data lives in the Paalvi folder on your computer:
- `backend/db.sqlite3`: products, settings, orders and enquiries
- `backend/media/`: all photos and videos

**Copy the whole Paalvi folder to a USB drive or Google Drive regularly.** If the computer is lost, so is the shop data.

---

## 8. Troubleshooting

| Problem | What to do |
|---|---|
| `START_PAALVI.bat` says setup failed | Install Python 3.12+ (tick *Add to PATH*) and Node.js 20+, restart the computer, try again |
| "That port is already in use" | The app is already running in another window. Use that window, or close it and start again |
| Website shows "We couldn't connect" | The black window was closed. Double-click `START_PAALVI.bat` |
| Photos don't show on the website | Close the black window and start `START_PAALVI.bat` again |
| Forgot the owner password | In the Paalvi folder, open a terminal and run `backend\.venv\Scripts\python backend\manage.py changepassword <username>` |
| Static build fails | Make sure Node.js is installed. Read the message shown; it explains what went wrong |
| Online product links show "Not found" | `.htaccess` is missing in `public_html`. Re-extract the ZIP there |
| Online site still shows old products | Build again, re-upload, then refresh with **Ctrl + F5** |
