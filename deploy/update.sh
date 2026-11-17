#!/usr/bin/env bash
# Pull the latest code from GitHub and refresh the live site.  Run on the server:
#   bash deploy/update.sh
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"
git pull --ff-only
backend/.venv/bin/pip install --quiet -r backend/requirements.txt
(cd frontend && npm ci && npm run build)
cd backend
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart paalvi
echo "Updated and restarted."
