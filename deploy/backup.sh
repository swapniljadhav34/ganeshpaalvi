#!/usr/bin/env bash
# Nightly backup of the database and uploaded photos/videos. Keeps the last 7 days.
# Installed by setup.sh. IMPORTANT: also copy ~/backups to another place now and then
# (your laptop, Google Drive...). A backup on the same server does not survive losing the server.
set -euo pipefail
APP_DIR="${APP_DIR:?APP_DIR not set}"
DEST="$HOME/backups"
STAMP="$(date +%Y-%m-%d)"
mkdir -p "$DEST"

# DATABASE_URL looks like postgres://user:pass@host:5432/db
DB_URL="$(grep '^DATABASE_URL=' "$APP_DIR/backend/.env" | cut -d= -f2-)"
pg_dump "$DB_URL" | gzip > "$DEST/db-$STAMP.sql.gz"
tar -czf "$DEST/media-$STAMP.tar.gz" -C "$APP_DIR/backend" media

find "$DEST" -name 'db-*.sql.gz' -mtime +7 -delete
find "$DEST" -name 'media-*.tar.gz' -mtime +7 -delete
echo "$(date -Is) backup ok"
