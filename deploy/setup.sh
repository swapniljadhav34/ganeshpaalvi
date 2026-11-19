#!/usr/bin/env bash
# Paalvi one-time server setup for any Ubuntu 22.04 / 24.04 VM:
#   Oracle Cloud (Always Free) · AWS EC2 / Lightsail · Hostinger VPS · DigitalOcean · any KVM VPS
#
#   sudo bash deploy/setup.sh shop.example.com you@example.com [--demo]
#
# Run it from inside the cloned repo, as your normal login user (with sudo). It installs
# PostgreSQL, Redis, nginx + free HTTPS, builds the site, starts it on boot, schedules the
# nightly job and backups, and hardens the server. Safe to re-run (it keeps your .env).
set -euo pipefail

DOMAIN="${1:?Usage: sudo bash deploy/setup.sh <domain> <email> [--demo]}"
EMAIL="${2:?Usage: sudo bash deploy/setup.sh <domain> <email> [--demo]}"
DEMO="${3:-}"

APP_USER="${SUDO_USER:?Run this with sudo from your normal login (not as root directly)}"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="$(getent passwd "$APP_USER" | cut -d: -f6)"
BACKEND="$APP_DIR/backend"
ENV_FILE="$BACKEND/.env"
as_user() { sudo -u "$APP_USER" -H "$@"; }
manage() { as_user bash -c "cd '$BACKEND' && PYTHONIOENCODING=utf-8 .venv/bin/python manage.py $*"; }
env_get() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2-; }
env_ensure() { grep -qE "^$1=" "$ENV_FILE" || echo "$1=$2" >> "$ENV_FILE"; }   # add a setting only if missing

echo "==> 1/11  Swap (lets the site build on 1 GB machines)"
if ! swapon --show | grep -q .; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> 2/11  System packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3-venv python3-dev build-essential libpq-dev nginx postgresql redis-server \
  certbot python3-certbot-nginx git curl iptables-persistent openssl fail2ban unattended-upgrades
if ! command -v node >/dev/null || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt 20 ]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi
systemctl enable --now redis-server fail2ban
dpkg-reconfigure -f noninteractive unattended-upgrades >/dev/null 2>&1 || true   # automatic security updates

echo "==> 3/11  Firewall: open web ports (Oracle & some VPS images block them inside the VM too)"
for port in 80 443; do
  iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null || iptables -I INPUT 5 -p tcp --dport "$port" -j ACCEPT
done
netfilter-persistent save >/dev/null || true

echo "==> 4/11  Database + settings (.env)"
if [ ! -f "$ENV_FILE" ]; then
  DB_PASS="$(openssl rand -hex 16)"
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'paalvi') THEN CREATE ROLE paalvi LOGIN PASSWORD '$DB_PASS';
  ELSE ALTER ROLE paalvi PASSWORD '$DB_PASS'; END IF;
END \$\$;
SQL
  sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='paalvi'" | grep -q 1 || sudo -u postgres createdb -O paalvi paalvi
  cat > "$ENV_FILE" <<ENV
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=$(openssl rand -hex 40)
DJANGO_ALLOWED_HOSTS=$DOMAIN,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://$DOMAIN
CORS_ALLOWED_ORIGINS=https://$DOMAIN
SITE_URL=https://$DOMAIN
DATABASE_URL=postgres://paalvi:$DB_PASS@127.0.0.1:5432/paalvi
ENV
  echo "    created $ENV_FILE"
fi
# Settings added by newer versions are appended without touching your existing values.
env_ensure REDIS_URL "redis://127.0.0.1:6379/1"
env_ensure CLIENT_IP_HEADER "HTTP_X_REAL_IP"
env_ensure ADMIN_URL "admin-$(openssl rand -hex 4)/"
env_ensure PRIVATE_MEDIA_ROOT "$BACKEND/private_media"
env_ensure USE_S3_MEDIA "false"
grep -q '^# AI_API_KEY' "$ENV_FILE" || cat >> "$ENV_FILE" <<'ENV'
# AI_API_KEY=        (free Groq key → switches on the conversational AI Care Guide)
# LEAD_NOTIFY_EMAILS=owner@example.com   ERROR_EMAILS=owner@example.com   SENTRY_DSN=
ENV
chown "$APP_USER":"$APP_USER" "$ENV_FILE" && chmod 600 "$ENV_FILE"
ADMIN_URL="$(env_get ADMIN_URL)"

echo "==> 5/11  Python packages"
as_user python3 -m venv "$BACKEND/.venv"
as_user "$BACKEND/.venv/bin/pip" install --quiet --upgrade pip
as_user "$BACKEND/.venv/bin/pip" install --quiet -r "$BACKEND/requirements.txt"

echo "==> 6/11  Building the website (a few minutes)"
as_user bash -c "cd '$APP_DIR/frontend' && npm ci && npm run build"
as_user "$BACKEND/.venv/bin/python" -m whitenoise.compress "$APP_DIR/frontend/dist" >/dev/null   # .gz + .br copies

echo "==> 7/11  Database tables, themes, thumbnails, static files"
mkdir -p "$BACKEND/media" "$BACKEND/private_media" "$HOME_DIR/backups"
chown -R "$APP_USER":"$APP_USER" "$BACKEND/media" "$BACKEND/private_media" "$HOME_DIR/backups"
chmod 750 "$BACKEND/private_media"
manage migrate --noinput
manage seed_themes
if [ "$DEMO" = "--demo" ]; then
  manage seed_demo
  manage seed_ops
fi
manage generateimages >/dev/null
manage collectstatic --noinput >/dev/null
chmod -R a+rX "$BACKEND/media" "$APP_DIR/frontend/dist"
chmod o+x "$HOME_DIR" "$APP_DIR" "$BACKEND" "$APP_DIR/frontend"   # nginx may enter (not list) these folders

echo "==> 8/11  App service (starts on boot, restarts on crash)"
cat > /etc/systemd/system/paalvi.service <<UNIT
[Unit]
Description=Paalvi website
After=network.target postgresql.service redis-server.service

[Service]
User=$APP_USER
WorkingDirectory=$BACKEND
# Threads let slow calls (AI guide, email) wait without blocking other visitors.
ExecStart=$BACKEND/.venv/bin/gunicorn config.wsgi --workers 2 --worker-class gthread --threads 8 --timeout 60 \\
  --bind 127.0.0.1:8000 --max-requests 2000 --max-requests-jitter 200 --access-logfile - --error-logfile -
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable paalvi
systemctl restart paalvi

echo "==> 9/11  nginx (compression, caching, sandboxed uploads, login rate limits)"
cat > /etc/nginx/conf.d/paalvi-limits.conf <<'NGINX'
limit_req_zone $binary_remote_addr zone=paalvi_login:10m rate=10r/m;
NGINX
cat > /etc/nginx/sites-available/paalvi <<NGINX
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 30M;   # 3D models up to 20 MB, hero videos up to 10 MB
    server_tokens off;

    gzip on;
    gzip_vary on;
    gzip_comp_level 5;
    gzip_min_length 512;
    gzip_types text/css application/javascript application/json image/svg+xml text/plain application/xml model/gltf-binary;

    # Built JS/CSS: file names change on every build → cache for a year.
    location /assets/ {
        alias $APP_DIR/frontend/dist/assets/;
        gzip_static on;
        expires 1y;
        add_header Cache-Control "public, max-age=31536000, immutable";
        access_log off;
    }

    # Uploads: never executed as a web page (sandboxed), correct type for .glb 3D models.
    location /media/ {
        alias $BACKEND/media/;
        types { model/gltf-binary glb; image/webp webp; image/svg+xml svg; video/mp4 mp4; video/webm webm; image/png png; image/jpeg jpg jpeg; }
        default_type application/octet-stream;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Content-Security-Policy "default-src 'none'; img-src 'self' data:; media-src 'self'; style-src 'unsafe-inline'; sandbox" always;
        expires 30d;
        add_header Cache-Control "public";
        access_log off;
    }

    # Slow down password guessing (django-axes also locks accounts after 5 wrong tries).
    location ~ ^/(api/staff/auth/login|${ADMIN_URL}login/)\$ {
        limit_req zone=paalvi_login burst=10 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/paalvi /etc/nginx/sites-enabled/paalvi
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "==> 10/11  HTTPS certificate"
if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" --redirect; then
  echo "    HTTPS is on (renews automatically)."
else
  echo "    !! HTTPS not set up yet — the domain almost certainly doesn't point at this server yet."
  echo "       Fix the DNS 'A' record, wait a few minutes, then run:"
  echo "       sudo certbot --nginx -d $DOMAIN -m $EMAIL --agree-tos --redirect"
fi

echo "==> 11/11  Nightly job + backups"
install -m 755 "$APP_DIR/deploy/backup.sh" /usr/local/bin/paalvi-backup
cat > /etc/cron.d/paalvi <<CRON
# Nightly: inventory alerts (expiry), overdue invoices, analytics clean-up
15 2 * * * $APP_USER cd $BACKEND && .venv/bin/python manage.py run_daily >> $HOME_DIR/backups/daily.log 2>&1
# Nightly backup of database, photos and private receipts
30 2 * * * $APP_USER APP_DIR=$APP_DIR /usr/local/bin/paalvi-backup >> $HOME_DIR/backups/backup.log 2>&1
CRON

cat <<DONE

==========================================================
 Paalvi is running at   https://$DOMAIN
 Staff Studio:          https://$DOMAIN/studio
 Site admin (owner):    https://$DOMAIN/$ADMIN_URL      ← keep this address private

 Next: create the owner login
   cd $BACKEND && .venv/bin/python manage.py createsuperuser
 Update later:          bash $APP_DIR/deploy/update.sh
 Settings file:         $ENV_FILE
==========================================================
DONE
