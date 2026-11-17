web: cd backend && gunicorn config.wsgi --workers 2 --timeout 60
release: cd backend && python manage.py migrate --noinput && python manage.py collectstatic --noinput
