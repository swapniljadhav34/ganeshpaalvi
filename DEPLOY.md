# Deploying Paalvi

Paalvi is one Django app that also serves the built React site. Pick the route that matches your host.

| Host | Route | Cost | Notes |
|---|---|---|---|
| **Oracle Cloud Always Free** | A — `deploy/setup.sh` | ₹0 | Best value. Permanent disk; DB, photos and site on one VM. |
| **AWS EC2 / Lightsail** | A — `deploy/setup.sh` (or B — Docker) | from ~$5/mo | Lightsail is simplest. RDS/S3 optional. |
| **Hostinger VPS (KVM)** | A — `deploy/setup.sh` | from ~₹400/mo | **VPS only** — Hostinger *shared/web* hosting can't run Django. |
| DigitalOcean / Linode / any Ubuntu VPS | A or B | from ~$5/mo | |
| Any Docker host | B — `docker compose` | — | Caddy gives automatic HTTPS. |
| Heroku / Render | C — Procfile | ~$10+/mo | No permanent disk → needs S3/R2 for photos and receipts. |

Before any route: put the code on GitHub (private repo) and point your domain's **A record** at the server's public IP.

---

## A. Ubuntu VM (Oracle, AWS EC2/Lightsail, Hostinger VPS, DigitalOcean)

**1. Create the server** — Ubuntu 22.04 or 24.04, 1 GB RAM minimum (2 GB+ recommended).
- *Oracle*: Compute → Instances → Create → Image **Ubuntu**, shape **VM.Standard.A1.Flex** (2 OCPU / 12 GB, Always Free) or **E2.1.Micro**. Download the SSH key.
  Then **Networking → your VCN → Security List → Add ingress rules**: TCP **80** and **443** from `0.0.0.0/0`.
- *AWS Lightsail*: Create instance → Linux/Unix → OS only → **Ubuntu**. Networking tab → add **HTTPS (443)**. Attach a static IP.
- *AWS EC2*: Launch Ubuntu, security group allowing 22 (your IP), 80, 443. Allocate an Elastic IP.
- *Hostinger VPS*: Choose **Ubuntu 24.04** template; ports are open by default.

**2. Point the domain** — DNS `A` record: `shop.yourdomain.in → <server IP>` (and `www` if you use it). Wait until `ping shop.yourdomain.in` shows the IP.

**3. Install**
```bash
ssh ubuntu@<server-ip>                      # Oracle/AWS user is 'ubuntu'; Hostinger is 'root' → create a user first:
#   adduser paalvi && usermod -aG sudo paalvi && su - paalvi
git clone https://github.com/<you>/paalvi.git && cd paalvi     # private repo: use a GitHub token as the password
sudo bash deploy/setup.sh shop.yourdomain.in you@email.com      # add --demo to load sample products
cd backend && .venv/bin/python manage.py createsuperuser        # the owner login
```
The script prints your **Studio** address (`/studio`) and your private **admin** address (`/admin-xxxx/`, random — keep it private).

**4. Update after changes** — push to GitHub, then on the server: `bash deploy/update.sh`.

What the script sets up: PostgreSQL, Redis, gunicorn (threaded) under systemd, nginx with gzip and year-long caching for built files, sandboxed `/media/` (uploads can never run as web pages), login rate limiting, free HTTPS (auto-renew), fail2ban, automatic security updates, a nightly job (`run_daily`: inventory alerts, overdue invoices, analytics clean-up) and nightly backups to `~/backups` (database, photos, private receipts; 7 days).

> **Copy backups off the server.** Install rclone, run `rclone config`, then add `BACKUP_REMOTE=<remote>:<bucket>` to `backend/.env` — the nightly backup will copy itself there.

## B. Docker (any host with Docker)

```bash
git clone https://github.com/<you>/paalvi.git && cd paalvi
cp backend/.env.example backend/.env       # set DJANGO_SECRET_KEY, SITE_URL, DJANGO_ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS
export DOMAIN=shop.yourdomain.in POSTGRES_PASSWORD=$(openssl rand -hex 16)   # keep this password safe
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_demo   # optional sample data
```
Services: `web` (gunicorn), `db` (PostgreSQL 16), `redis`, `scheduler` (nightly job) and `caddy` (automatic HTTPS, serves `/media/`). Data lives in Docker volumes `pgdata`, `media`, `private` — back them up (e.g. `docker compose exec db pg_dump -U paalvi paalvi > backup.sql`).

## C. Heroku / Render (no permanent disk)

1. Buildpacks: `heroku/nodejs` then `heroku/python` (the root `package.json` builds the site; the root `Procfile` runs it).
2. Add PostgreSQL and (recommended) Redis add-ons.
3. Config vars: everything in `backend/.env.example`, plus **`CLIENT_IP_HEADER=XFF_RIGHTMOST`**.
4. Media **must** live in object storage: `USE_S3_MEDIA=true` + `S3_*` (Cloudflare R2 or AWS S3), and **`S3_PRIVATE_BUCKET_NAME`** — a *separate, non-public* bucket for expense receipts.
5. Schedule `cd backend && python manage.py run_daily` once a day (Heroku Scheduler).

---

## Production checklist

- [ ] `DJANGO_DEBUG=false` and a long random `DJANGO_SECRET_KEY` (the site refuses to start without one)
- [ ] Owner login created; the local test login `admin` / `paalvi-admin-123` does **not** exist on the server (it only lives in your laptop's database)
- [ ] `ADMIN_URL` is not `admin/` (setup.sh does this for you)
- [ ] Brand & Contact: real WhatsApp number, email, GSTIN, address, privacy policy text
- [ ] Studio → Team: add each employee with the right role (they get a one-time password)
- [ ] Inventory: real opening stock entered (Studio → Inventory → ± Stock → "Delivery…"), thresholds checked
- [ ] Optional: `AI_API_KEY` (Groq free tier), `LEAD_NOTIFY_EMAILS`, `ERROR_EMAILS` or `SENTRY_DSN`
- [ ] Backups copied off the server (rclone `BACKUP_REMOTE`)
- [ ] Phone test: home, product (3D), WhatsApp button, enquiry form, Studio login

## 3D models in production

- Upload `.glb` (binary glTF) files — max 20 MB (`MAX_3D_MODEL_MB`), ideally under 5 MB (compress at gltf.report).
- MIME type `model/gltf-binary` is set by nginx (`deploy/setup.sh`), Caddy (`deploy/Caddyfile`) and Django.
- If photos/models are on another domain (R2/S3/CDN), allow the site to fetch them — R2/S3 **CORS policy**:
  `[{"AllowedOrigins": ["https://shop.yourdomain.in"], "AllowedMethods": ["GET", "HEAD"], "AllowedHeaders": ["*"], "MaxAgeSeconds": 86400}]`
  and serve `.glb` with `Content-Type: model/gltf-binary`.

## Running the tests

```bash
cd backend && python manage.py test          # 27 tests: permissions, stock, production, accounting, security fixes
```
