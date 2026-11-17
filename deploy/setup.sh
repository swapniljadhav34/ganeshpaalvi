#!/usr/bin/env bash
# Paalvi one-time server setup for an Ubuntu VM (Oracle Cloud Always Free).
#
#   sudo bash deploy/setup.sh demo.paalvi.in you@example.com [--demo]
#
# Run it from inside the cloned repo. It installs everything, builds the site, starts it
# automatically on boot, turns on HTTPS and schedules nightly backups. Safe to re-run.
set -euo pipefail

DOMAIN="${1:?Usage: sudo bash deploy/setup.sh <domain> <email> [--demo]}"
EMAIL="${2:?Usage: sudo bash deploy/setup.sh <domain> <email> [--demo]}"
DEMO="${3:-}"

APP_USER="${SUDO_USER:?Run this with sudo from your normal login (not as root directly)}"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="$(getent passwd "$APP_USER" | cut -d: -f6)"
BACKEND="$APP_DIR/backend"
as_user() { sudo -u "$APP_USER" -H "$@"; }

echo "==> 1/9  Extra memory (swap) so the site can build on a small VM"
if ! swapon --show | grep -q .; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> 2/9  Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3-venv python3-dev build-essential libpq-dev nginx postgresql \
  certbot python3-certbot-nginx git curl iptables-persistent openssl
if ! command -v node >/dev/null || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt 20 ]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi

echo "==> 3/9  Opening web ports in the server's own firewall (Oracle blocks them by default)"
for port in 80 443; do
  iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null || iptables -I INPUT 5 -p tcp --dport "$port" -j ACCEPT
done
netfilter-persistent save >/dev/null

echo "==> 4/9  Database"
ENV_FILE="$BACKEND/.env"
if [ ! -f "$ENV_FILE" ]; then
  DB_PASS="$(openssl rand -hex 16)"
  SECRET="$(openssl rand -hex 32)"
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'paalvi') THEN CREATE ROLE paalvi LOGIN PASSWORD '$DB_PASS';
  ELSE ALTER ROLE paalvi PASSWORD '$DB_PASS'; END IF;
END \$\$;
SQL
  sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='paalvi'" | grep -q 1 || sudo -u postgres createdb -O paalvi paalvi
  cat > "$ENV_FILE" <<ENV
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=$SECRET
DJANGO_ALLOWED_HOSTS=$DOMAIN,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://$DOMAIN
CORS_ALLOWED_ORIGINS=https://$DOMAIN
SITE_URL=https://$DOMAIN
DATABASE_URL=postgres://paalvi:$DB_PASS@127.0.0.1:5432/paalvi
USE_S3_MEDIA=false
# AI_API_KEY=   (add a free Groq key here to switch on the AI Care Guide)
# LEAD_NOTIFY_EMAILS=owner@example.com
ENV
  chown "$APP_USER":"$APP_USER" "$ENV_FILE" && chmod 600 "$ENV_FILE"
  echo "    created $ENV_FILE"
else
  echo "    $ENV_FILE already exists - keeping it"
fi

echo "==> 5/9  Python packages"
as_user python3 -m venv "$BACKEND/.venv"
as_user "$BACKEND/.venv/bin/pip" install --quiet --upgrade pip
as_user "$BACKEND/.venv/bin/pip" install --quiet -r "$BACKEND/requirements.txt"

echo "==> 6/9  Building the website (takes a few minutes)"
as_user bash -c "cd '$APP_DIR/frontend' && npm ci && npm run build"

echo "==> 7/9  Setting up the site"
as_user bash -c "cd '$BACKEND' && .venv/bin/python manage.py migrate --noinput && .venv/bin/python manage.py seed_themes && .venv/bin/python manage.py collectstatic --noinput"
if [ "$DEMO" = "--demo" ]; then
  as_user bash -c "cd '$BACKEND' && PYTHONIOENCODING=utf-8 .venv/bin/python manage.py seed_demo"
fi
mkdir -p "$BACKEND/media" "$HOME_DIR/backups"
chown -R "$APP_USER":"$APP_USER" "$BACKEND/media" "$HOME_DIR/backups"
chmod -R a+rX "$BACKEND/media"
chmod o+x "$HOME_DIR"   # lets the web server reach the photos folder (it cannot list your files)

echo "==> 8/9  Starting the site automatically, and nginx"
cat > /etc/systemd/system/paalvi.service <<UNIT
[Unit]
Description=Paalvi website
After=network.target postgresql.service

[Service]
User=$APP_USER
WorkingDirectory=$BACKEND
ExecStart=$BACKEND/.venv/bin/gunicorn config.wsgi --workers 2 --timeout 60 --bind 127.0.0.1:8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now paalvi
systemctl restart paalvi

cat > /etc/nginx/sites-available/paalvi <<NGINX
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 60M;   # room for hero videos

    location /media/ {
        alias $BACKEND/media/;
        expires 30d;
        add_header Cache-Control "public";
        access_log off;
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

echo "==> 9/9  HTTPS certificate and nightly backups"
if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" --redirect; then
  echo "    HTTPS is on."
else
  echo "    !! HTTPS could not be set up yet. This almost always means the domain does not point at this server yet."
  echo "       Fix the DNS record, wait a few minutes, then run:  sudo certbot --nginx -d $DOMAIN -m $EMAIL --agree-tos --redirect"
fi
install -m 755 "$APP_DIR/deploy/backup.sh" /usr/local/bin/paalvi-backup
echo "30 2 * * * $APP_USER APP_DIR=$APP_DIR /usr/local/bin/paalvi-backup >> $HOME_DIR/backups/backup.log 2>&1" > /etc/cron.d/paalvi-backup

cat <<DONE

==========================================================
 Paalvi is running at  https://$DOMAIN
 Next: create your admin login
   cd $BACKEND && .venv/bin/python manage.py createsuperuser
 Then open  https://$DOMAIN/admin/
 Updating later:  bash $APP_DIR/deploy/update.sh
==========================================================
DONE
