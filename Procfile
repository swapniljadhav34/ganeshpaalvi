web: cd backend && gunicorn config.wsgi --workers 2 --worker-class gthread --threads 8 --timeout 60 --max-requests 2000 --max-requests-jitter 200
release: cd backend && python manage.py migrate --noinput && python manage.py seed_themes && python manage.py generateimages && python manage.py collectstatic --noinput
