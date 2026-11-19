#!/bin/sh
# Runs before the web server starts: apply database changes, make sure themes and thumbnails exist.
set -e
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
  python manage.py seed_themes >/dev/null
  python manage.py generateimages >/dev/null 2>&1 || true
fi
exec "$@"
