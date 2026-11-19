# Platform reference: roles, orders, languages, maintenance

How the store's access control, order book, languages and system tools fit together. For developers and for the Admin.

## 1. One permission system, two workspaces

| Workspace | URL | Who | What |
|---|---|---|---|
| **Studio** | `/studio` | Everyone with a role | Order book, inventory, production, enquiries, accounts, products & 3D, traffic, directory, team & roles, system |
| **Designer** | `/<ADMIN_URL>/` | Anyone whose permissions include `site.design`, `catalog.edit` or `catalog.delete` | Visual site builder: brand, theme, header/footer, homepage builder (drag-and-drop order, animated hero/sections), translations, products |

Both read the **same permission matrix** (`ops.RoleDefinition`). There is no second set of Django group permissions to keep in sync:

- Studio APIs check permissions with `@needs("perm")` (`ops/permissions.py`).
- The Designer workspace asks Django `user.has_perm("storefront.change_pagesection")`. `ops/backends.py::RolePermissionBackend` answers that from the matrix, and the sidebar hides groups the person can't use.
- `StaffProfile.sync_user_flags()` keeps `is_superuser` (Admin role only) and `is_staff` (Designer access) in step whenever a role, its permissions or a person's extra permissions change.

### Roles (built-in; the Admin can add more)

| Role | Default permissions |
|---|---|
| **Admin** (`SUPER_ADMIN`) | Everything, always. Can't be reduced. |
| **Designer** | site.design, catalog.edit, catalog.media |
| Marketing team | orders.view/create, leads.view/update, analytics.view, inventory.view |
| Distribution team | orders.view/create/update, inventory.view, directory.view |
| Warehouse worker | orders.view/update, inventory.view/adjust |
| Supply-chain vendor | production.view |
| Accountant | accounting.view/edit/export, orders.view |
| Inventory manager | inventory.view/adjust/reset/batches, production.view, orders.view |
| Production manager | production.view/update/manage, inventory.view |
| Operations employee | inventory.view/adjust, production.view/update, leads.view/update, orders.view/update |
| Catalog & media employee | catalog.media, catalog.edit, inventory.view |
| Wholesale manager | leads.view/update, inventory.view, orders.view/create/update |

- **Delegation:** Studio → Team & roles → *Permissions* gives one person extra permissions (e.g. covering a colleague) without changing their role.
- **Admin-only, never delegable:** `staff.manage` (accounts and roles) and `system.maintain` (cache, recovery, reset). Anyone holding them could make themselves Admin. They are stripped from every non-Admin role even if written straight into the database.
- **Accounts:** the Admin can enable/disable any account (this switches the whole login off) or delete it permanently. Deleted people's past work stays and shows as a deleted user. The last Admin can't be disabled, demoted or deleted.

## 2. Data model (new and changed)

```
auth.User ─1:1─ ops.StaffProfile ── role ──> ops.RoleDefinition(key, label, permissions[], is_builtin)
                 extra_permissions[], kind (EMPLOYEE/WAREHOUSE/DISTRIBUTION/MARKETING/VENDOR), company, phone, city, is_active

ops.Order(number ORD-YYMMDD-NNNN, tracking_token, source, channel, status, stock_state,
          customer…, subtotal/discount/shipping/total, payment_status, courier, tracking_number, lead→leads.LeadInquiry)
  ├─ ops.OrderLine(product→catalog.Product SET_NULL, item→ops.InventoryItem SET_NULL, title/sku snapshot, quantity, unit_price)
  └─ ops.OrderEvent(status, note, by, at)          ← the customer-visible timeline

ops.StockMovement.item  → SET_NULL + item_label    (deleting a product keeps its stock history)
ops.ProductionBatch.item→ SET_NULL + item_label

storefront.BrandSettings + shop_title, shop_intro, search_placeholder, default_language, show_language_picker
storefront.UiTranslation(language, key, text)    ← Designer overrides for any built-in website word
```

### Order status and stock

`PENDING → CONFIRMED → PACKED → IN_TRANSIT → DELIVERED`, plus `CANCELLED`. Orders only move forward. Every stock change goes through `ops.inventory.adjust_stock` (locked, logged, alerts re-checked):

| Move | Stock effect |
|---|---|
| → Confirmed / Packed | pieces **reserved** (fails if not enough available) |
| → In transit / Delivered | pieces **leave stock** (OUT, or WHOLESALE_DISPATCH for wholesale) |
| Cancel before dispatch | reservation released |
| Cancel in transit | pieces **returned** to stock |

## 3. API routes added

Staff (`/api/staff/…`, session + CSRF, permission in brackets):

| Method | Path | Permission |
|---|---|---|
| GET | `/orders` · `/orders/{id}` · `/orders/customers` | orders.view |
| GET | `/orders/{id}/receipt?size=a4\|thermal` (print-ready HTML → Save as PDF) | orders.view |
| GET | `/orders/pick/products` · POST `/orders` | orders.create |
| PATCH | `/orders/{id}` · POST `/orders/{id}/status` · DELETE `/orders/{id}` (pending only) | orders.update |
| DELETE | `/catalog/products/{id}` | catalog.delete |
| GET/POST/PATCH | `/catalog/categories[/{id}]` | catalog.edit |
| DELETE | `/catalog/categories/{id}?move_to=ID \| delete_products=true` | catalog.delete |
| POST | `/inventory/items/{id}/zero` · `/catalog/products/{id}/zero-stock` | inventory.reset |
| GET | `/directory?kind=&q=` | directory.view |
| GET/POST/PATCH/DELETE | `/team`, `/team/{id}`, `/team/{id}/reset-password` | staff.manage |
| POST/PATCH/DELETE | `/roles`, `/roles/{key}` | staff.manage |
| GET | `/system/health` | system.maintain |
| POST | `/system/clear-cache` · `/system/recover` · `/system/reset` (needs `confirm: "RESET"` + password) | system.maintain |

Public (rate-limited, no login): `GET /api/orders/track?number=&phone=`, `GET /api/orders/track/{token}`, `GET /api/orders/track/{token}/receipt`. Customers never see phone numbers, internal notes or staff names. Pages: `/track` and `/track/<token>` (noindex).

## 4. Languages

- English plus all 22 Eighth-Schedule languages (`storefront/languages.py`). The picker sits in the header; Urdu, Sindhi and Kashmiri switch the page to right-to-left.
- Built-in words: `frontend/src/i18n/strings.js` (one list per language, same key order). Lookup order: Designer override (Designer → Translations) › built-in › English.
- Built-in translations are machine-drafted. **Have a native speaker check them before launch.** Santali, Manipuri, Bodo and Kashmiri have no built-in words yet and show English until translations are added in the Designer.
- Product and section text you write is shown as written; translate it per language through Translations or by writing bilingual content.

## 5. Brand name

Nothing is hard-coded. The brand name, search placeholder, catalogue heading ("Shop <brand>"), header, footer, receipts, Studio and Designer titles, WhatsApp greeting and SEO tags all come from **Brand & contact details**. When the name is empty, neutral wording is used. The product catalogue is always rendered on the homepage, and no setting or role can switch it off.

## 6. System tools (Admin only, no restart)

- **Clear cache:** cached homepage/product data, role matrix and the cached `index.html`.
- **Recovery:** clear caches → re-check every stock alert and website stock label → overdue invoices → remove expired sessions → lift login lockouts → database check. Each step reports separately, and one failed step doesn't stop the others.
- **Reset site:** writes `backend/backups/before-reset-*.json`, then removes all content and blanks the brand text. Accounts, roles and the matrix are kept. Optionally reloads the sample content. CLI: `python manage.py reset_site --yes [--sample]`. Restore a backup with `python manage.py loaddata backups/<file>.json`.

## 7. Tests

`python manage.py test`: 47 tests, including `ops/tests_platform.py` (matrix, delegation, Designer access, account deletion, last-Admin protection, order stock flow, public tracking, receipts, product deletion keeping history, zero stock, categories, system tools and guarded reset).
