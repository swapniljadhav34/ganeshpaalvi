#!/usr/bin/env bash
# Nightly backup of the database, uploaded photos/videos and private receipts. Keeps 7 days.
# Installed by setup.sh.
#
# A backup on the same server does NOT survive losing the server. Copy ~/backups elsewhere:
#   • set BACKUP_REMOTE in backend/.env to an rclone remote (e.g. r2:paalvi-backups) after `rclone config`, or
#   • download the folder to your laptop now and then (scp / WinSCP).
set -euo pipefail
APP_DIR="${APP_DIR:?APP_DIR not set}"
ENV_FILE="$APP_DIR/backend/.env"
DEST="$HOME/backups"
STAMP="$(date +%Y-%m-%d)"
mkdir -p "$DEST"
umask 077   # backups contain customer data — readable only by this user

env_get() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2-; }
DB_URL="$(env_get DATABASE_URL)"
if [ -n "$DB_URL" ]; then
  pg_dump "$DB_URL" | gzip > "$DEST/db-$STAMP.sql.gz"
else
  cp "$APP_DIR/backend/db.sqlite3" "$DEST/db-$STAMP.sqlite3"
fi
tar -czf "$DEST/media-$STAMP.tar.gz" -C "$APP_DIR/backend" media
[ -d "$APP_DIR/backend/private_media" ] && tar -czf "$DEST/private-$STAMP.tar.gz" -C "$APP_DIR/backend" private_media

find "$DEST" -name 'db-*' -mtime +7 -delete
find "$DEST" -name 'media-*.tar.gz' -mtime +7 -delete
find "$DEST" -name 'private-*.tar.gz' -mtime +7 -delete

REMOTE="$(env_get BACKUP_REMOTE || true)"
if [ -n "$REMOTE" ] && command -v rclone >/dev/null; then
  rclone copy "$DEST" "$REMOTE" --include "*-$STAMP*" && echo "$(date -Is) copied off-server to $REMOTE"
fi
echo "$(date -Is) backup ok"
