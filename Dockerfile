# Paalvi — one image with the Django API/admin and the built React site.
#   docker build -t paalvi .
# Used by docker-compose.yml (with PostgreSQL, Redis and Caddy for HTTPS).

# ---- 1. Build the React site ----
FROM node:20-alpine AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2. Python app ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
COPY --from=web /app/frontend/dist /app/frontend/dist
# Pre-compress JS/CSS (gzip + brotli) and collect admin static files at build time.
RUN python -m whitenoise.compress /app/frontend/dist \
 && DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput
RUN useradd --create-home --uid 1000 paalvi \
 && mkdir -p media private_media \
 && chown -R paalvi:paalvi media private_media /app/frontend/dist
COPY deploy/docker-entrypoint.sh /usr/local/bin/paalvi-entrypoint
RUN chmod +x /usr/local/bin/paalvi-entrypoint
USER paalvi
EXPOSE 8000
ENTRYPOINT ["paalvi-entrypoint"]
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "2", "--worker-class", "gthread", "--threads", "8", \
     "--timeout", "60", "--max-requests", "2000", "--max-requests-jitter", "200", "--access-logfile", "-"]
