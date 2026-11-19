#!/usr/bin/env bash
# Pull the latest code from GitHub and refresh the live site (zero manual steps).  On the server:
#   bash deploy/update.sh
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"
git pull --ff-only
backend/.venv/bin/pip install --quiet -r backend/requirements.txt
(cd frontend && npm ci && npm run build)
backend/.venv/bin/python -m whitenoise.compress frontend/dist >/dev/null
chmod -R a+rX frontend/dist
cd backend
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py generateimages >/dev/null
.venv/bin/python manage.py collectstatic --noinput >/dev/null
.venv/bin/python manage.py check --deploy --fail-level ERROR
sudo systemctl restart paalvi
echo "Updated and restarted."
