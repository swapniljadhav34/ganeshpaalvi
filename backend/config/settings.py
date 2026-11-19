"""
Paalvi — Django settings.

Everything that changes between your laptop and the live server is read from
environment variables (see `.env.example`). Sensible local defaults mean you can
run the project with zero configuration.
"""

import os
from pathlib import Path

import mimetypes
from datetime import timedelta

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from django.templatetags.static import static
from django.urls import reverse_lazy
from dotenv import load_dotenv
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Refuse absurdly large photos (decompression bombs) before they eat the server's memory.
Image.MAX_IMAGE_PIXELS = 60_000_000
# .glb 3D models must be served with the right type or browsers refuse them.
mimetypes.add_type("model/gltf-binary", ".glb")


def env_bool(name, default=False):
    """Read 'true/false/1/0/yes/no' style environment variables."""
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    """Read comma-separated environment variables into a clean list."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# --- Core -------------------------------------------------------------------
# Fail closed: production is the default. Your laptop's backend/.env sets DJANGO_DEBUG=true.
DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY") or ("dev-only-insecure-key" if DEBUG else "")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is not set. Add it to backend/.env (see .env.example).")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,paalvi.in,www.paalvi.in,api.paalvi.in")
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS", "https://paalvi.in,https://www.paalvi.in,https://api.paalvi.in"
)

# Public site address — used for sitemap links, share links and "View on site".
SITE_URL = os.getenv("SITE_URL", "http://localhost:5173" if DEBUG else "https://paalvi.in").rstrip("/")
# Where uploaded photos are publicly reachable. Same as the site unless media lives elsewhere.
MEDIA_BASE_URL = os.getenv("MEDIA_BASE_URL", SITE_URL).rstrip("/")
# Admin address. Moving it away from /admin/ cuts automated login attacks.
ADMIN_URL = os.getenv("ADMIN_URL", "admin/").strip("/") + "/"
# Where Studio and the Designer live. In development they run on Django (:8000) while the website runs on Vite (:5173).
STAFF_URL = os.getenv("STAFF_URL", "http://127.0.0.1:8000" if DEBUG else SITE_URL).rstrip("/")

# Which request header holds the real visitor IP (set by YOUR proxy, never by the visitor):
#   HTTP_X_REAL_IP          nginx (deploy/setup.sh, docker)        — default
#   HTTP_CF_CONNECTING_IP   Cloudflare in front
#   XFF_RIGHTMOST           Heroku / AWS ALB (last X-Forwarded-For entry)
#   REMOTE_ADDR             no proxy at all
CLIENT_IP_HEADER = os.getenv("CLIENT_IP_HEADER", "HTTP_X_REAL_IP")

INSTALLED_APPS = [
    # Unfold must come before django.contrib.admin so its beautiful theme wins.
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.import_export",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Third-party helpers
    "corsheaders",
    "import_export",
    "imagekit",
    "axes",
    # Paalvi apps
    "storefront",
    "catalog",
    "leads",
    "ops",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",  # must be last: blocks locked-out logins
]

# --- Login protection: 5 wrong passwords for a username from one IP → locked for 1 hour ---
# RolePermissionBackend: the Designer workspace (this admin) reads the same permission matrix as Studio.
AUTHENTICATION_BACKENDS = ["axes.backends.AxesStandaloneBackend", "django.contrib.auth.backends.ModelBackend",
                           "ops.backends.RolePermissionBackend"]
AXES_FAILURE_LIMIT = int(os.getenv("AXES_FAILURE_LIMIT", "5"))
AXES_COOLOFF_TIME = timedelta(hours=1)
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_CLIENT_IP_CALLABLE = "api.ratelimit.client_ip"
AXES_VERBOSE = False

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database: PostgreSQL in production, SQLite on your laptop ---------------
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}
IS_POSTGRES = DATABASES["default"]["ENGINE"].endswith("postgresql")

# --- Cache: Redis if REDIS_URL is set, otherwise a shared file cache ---------
REDIS_URL = os.getenv("REDIS_URL", "")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient", "IGNORE_EXCEPTIONS": True},
        }
    }
else:
    # File cache is shared by every Gunicorn worker on the server, so an admin save
    # instantly refreshes the site for everyone (an in-memory cache would be per-worker).
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": os.getenv("CACHE_DIR", str(BASE_DIR / ".cache")),
            "OPTIONS": {"MAX_ENTRIES": 5000},
        }
    }

# Tests get their own throwaway cache so they can never overwrite the real site's cached pages.
if len(os.sys.argv) > 1 and os.sys.argv[1] == "test":
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = f"/{ADMIN_URL}login/"
LOGIN_REDIRECT_URL = f"/{ADMIN_URL}"

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# --- Static & media ---------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Optional: store uploads on Cloudflare R2 / any S3-compatible bucket.
USE_S3_MEDIA = env_bool("USE_S3_MEDIA", False)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}
if USE_S3_MEDIA:
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": os.getenv("S3_BUCKET_NAME"),
            "endpoint_url": os.getenv("S3_ENDPOINT_URL"),
            "access_key": os.getenv("S3_ACCESS_KEY_ID"),
            "secret_key": os.getenv("S3_SECRET_ACCESS_KEY"),
            "custom_domain": os.getenv("S3_CUSTOM_DOMAIN") or None,
            "default_acl": None,
            "querystring_auth": False,
            "file_overwrite": False,
        },
    }

# Private files (expense receipts) — never under /media/, only downloadable through a permission check.
PRIVATE_MEDIA_ROOT = Path(os.getenv("PRIVATE_MEDIA_ROOT", BASE_DIR / "private_media"))
# Hosts without a permanent disk: a SEPARATE non-public bucket for receipts (same S3_* credentials).
S3_PRIVATE_BUCKET_NAME = os.getenv("S3_PRIVATE_BUCKET_NAME", "")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "")

# Built React app (frontend/dist). When present, Django can serve it with
# server-rendered share previews for WhatsApp / Facebook (see api/seo.py).
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", BASE_DIR.parent / "frontend" / "dist"))
# WhiteNoise serves the built JS/CSS compressed (gzip + brotli) with year-long caching,
# so hosts without nginx (Heroku, App Runner, Render…) are fast too.
if FRONTEND_DIST.is_dir():
    WHITENOISE_ROOT = FRONTEND_DIST


def _immutable(path, url):
    """Vite's /assets/* and Django's hashed static files never change → cache for a year."""
    import re

    return url.startswith("/assets/") or bool(re.search(r"\.[0-9a-f]{12}\.\w+$", url))


WHITENOISE_IMMUTABLE_FILE_TEST = _immutable

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000
# Files above 5 MB stream to a temp file instead of RAM (keeps a 1 GB server safe).
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
MAX_3D_MODEL_MB = int(os.getenv("MAX_3D_MODEL_MB", "20"))

# --- CORS: only paalvi.in may call the API from a browser --------------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "https://paalvi.in,https://www.paalvi.in")
if DEBUG:
    CORS_ALLOWED_ORIGINS += ["http://localhost:5173", "http://127.0.0.1:5173"]
    # The Vite dev server proxies /api, so Studio logins arrive with the :5173 origin.
    CSRF_TRUSTED_ORIGINS += ["http://localhost:5173", "http://127.0.0.1:5173"]

# --- Security for production ------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", str(60 * 60 * 24 * 30)))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
# Staff sessions: 12 hours, ended when the browser closes is too annoying on phones.
SESSION_COOKIE_AGE = 60 * 60 * 12
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# --- Email (new-lead notifications) ----------------------------------------
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Paalvi <no-reply@paalvi.in>")
LEAD_NOTIFY_EMAILS = env_list("LEAD_NOTIFY_EMAILS", "")
EMAIL_TIMEOUT = 5  # an unreachable mail server must never hang a web worker
SERVER_EMAIL = DEFAULT_FROM_EMAIL
ADMINS = [("Owner", e) for e in env_list("ERROR_EMAILS", "")]

# --- AI concierge (any OpenAI-compatible provider) ---------------------------
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.groq.com/openai/v1")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "llama-3.1-8b-instant")
AI_TIMEOUT_SECONDS = float(os.getenv("AI_TIMEOUT_SECONDS", "12"))

# --- Rate limits (requests per minute per visitor IP) ------------------------
# Indian mobile networks put many people behind one IP, so these are generous.
RATE_LIMIT_AI_PER_MIN = int(os.getenv("RATE_LIMIT_AI_PER_MIN", "15"))
RATE_LIMIT_INQUIRY_PER_MIN = int(os.getenv("RATE_LIMIT_INQUIRY_PER_MIN", "12"))
RATE_LIMIT_CATALOG_PER_MIN = int(os.getenv("RATE_LIMIT_CATALOG_PER_MIN", "180"))
RATE_LIMIT_TRACK_PER_MIN = int(os.getenv("RATE_LIMIT_TRACK_PER_MIN", "120"))
RATE_LIMIT_TRACK_ORDER_PER_MIN = int(os.getenv("RATE_LIMIT_TRACK_ORDER_PER_MIN", "20"))  # public order tracking (per IP)
RATE_LIMIT_LOGIN_PER_MIN = int(os.getenv("RATE_LIMIT_LOGIN_PER_MIN", "10"))

# --- Inventory & analytics -------------------------------------------------------
TRAFFIC_RETENTION_DAYS = int(os.getenv("TRAFFIC_RETENTION_DAYS", "180"))

# --- Error reporting (optional): set SENTRY_DSN to get an alert for every server error ---
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=float(os.getenv("SENTRY_TRACES", "0.0")),
                    send_default_pii=False, environment="development" if DEBUG else "production")

# --- Admin look & feel (django-unfold) --------------------------------------
UNFOLD = {
    # Titles follow the brand name set in Brand & contact details (nothing hard-coded).
    "SITE_TITLE": "storefront.utils.designer_title",
    "SITE_HEADER": "storefront.utils.designer_title",
    "SITE_SUBHEADER": "Design your website",
    "SITE_SYMBOL": "spa",
    "SITE_URL": SITE_URL,
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "DASHBOARD_CALLBACK": "storefront.dashboard.dashboard_callback",
    "STYLES": [lambda request: static("admin/paalvi-admin.css")],
    # The sidebar search (Ctrl+K) also searches inside products, sections, leads… not just page names.
    "COMMAND": {"search_models": True, "show_history": True},
    "COLORS": {
        # Seafoam-mint primary so the admin feels like the brand.
        "primary": {
            "50": "#eef8f5", "100": "#d7efe8", "200": "#b5e0d4", "300": "#8fc9b9",
            "400": "#66ae9b", "500": "#4a9482", "600": "#3a7769", "700": "#315f55",
            "800": "#2a4d46", "900": "#25403b", "950": "#122421",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Overview",
                "items": [
                    {"title": "Dashboard", "icon": "space_dashboard", "link": reverse_lazy("admin:index")},
                ],
            },
            {
                "title": "Brand & Contact",
                "collapsible": True,
                "items": [
                    {"title": "Brand & contact details", "icon": "storefront",
                     "link": reverse_lazy("admin:storefront_brandsettings_changelist"), "permission": "ops.roles.can_design"},
                ],
            },
            {
                "title": "Theme & Festival Studio",
                "collapsible": True,
                "items": [
                    {"title": "Active theme & schedule", "icon": "palette",
                     "link": reverse_lazy("admin:storefront_activetheme_changelist"), "permission": "ops.roles.can_design"},
                    {"title": "Theme presets", "icon": "format_paint",
                     "link": reverse_lazy("admin:storefront_themepreset_changelist"), "permission": "ops.roles.can_design"},
                ],
            },
            {
                "title": "Site Design Studio",
                "collapsible": True,
                "items": [
                    {"title": "Shapes, motion, header & footer", "icon": "animation",
                     "link": reverse_lazy("admin:storefront_sitedesign_changelist"), "permission": "ops.roles.can_design"},
                    {"title": "Header menu links", "icon": "menu",
                     "link": reverse_lazy("admin:storefront_navlink_changelist"), "permission": "ops.roles.can_design"},
                    {"title": "Translations (Indian languages)", "icon": "translate",
                     "link": reverse_lazy("admin:storefront_uitranslation_changelist"), "permission": "ops.roles.can_design"},
                    {"title": "Footer columns & links", "icon": "view_column",
                     "link": reverse_lazy("admin:storefront_footercolumn_changelist"), "permission": "ops.roles.can_design"},
                ],
            },
            {
                "title": "Homepage Builder",
                "collapsible": True,
                "items": [
                    {"title": "Hero slides", "icon": "movie",
                     "link": reverse_lazy("admin:storefront_heroslide_changelist"), "permission": "ops.roles.can_design"},
                    {"title": "Page sections", "icon": "view_agenda",
                     "link": reverse_lazy("admin:storefront_pagesection_changelist"), "permission": "ops.roles.can_design"},
                ],
            },
            {
                "title": "Products",
                "collapsible": True,
                "items": [
                    {"title": "Products", "icon": "inventory_2",
                     "link": reverse_lazy("admin:catalog_product_changelist"), "permission": "ops.roles.can_edit_catalog"},
                    {"title": "Categories", "icon": "category",
                     "link": reverse_lazy("admin:catalog_category_changelist"), "permission": "ops.roles.can_edit_catalog"},
                    {"title": "Ingredients", "icon": "eco",
                     "link": reverse_lazy("admin:catalog_ingredient_changelist"), "permission": "ops.roles.can_edit_catalog"},
                    {"title": "Badges (free-from, vegan…)", "icon": "verified",
                     "link": reverse_lazy("admin:catalog_badge_changelist"), "permission": "ops.roles.can_edit_catalog"},
                    {"title": "Variants (all products)", "icon": "tune",
                     "link": reverse_lazy("admin:catalog_productvariant_changelist"), "permission": "ops.roles.can_edit_catalog"},
                    {"title": "Pack sizes (all products)", "icon": "package_2",
                     "link": reverse_lazy("admin:catalog_packageoption_changelist"), "permission": "ops.roles.can_edit_catalog"},
                ],
            },
            {
                "title": "Leads & Enquiries",
                "collapsible": True,
                "items": [
                    {"title": "All enquiries", "icon": "contact_phone",
                     "link": reverse_lazy("admin:leads_leadinquiry_changelist"), "permission": "ops.roles.can_see_leads"},
                ],
            },
            {
                "title": "AI Concierge",
                "collapsible": True,
                "items": [
                    {"title": "Care Guide settings", "icon": "smart_toy",
                     "link": reverse_lazy("admin:storefront_aiassistantconfig_changelist"), "permission": "ops.roles.can_design"},
                ],
            },
            {
                "title": "Operations",
                "collapsible": True,
                "items": [
                    {"title": "Open Studio ↗", "icon": "open_in_new", "link": f"{STAFF_URL}/studio", "permission": "ops.roles.is_admin"},
                    {"title": "Stock items", "icon": "inventory",
                     "link": reverse_lazy("admin:ops_inventoryitem_changelist"), "permission": "ops.roles.is_admin"},
                    {"title": "Stock movement log", "icon": "history",
                     "link": reverse_lazy("admin:ops_stockmovement_changelist"), "permission": "ops.roles.is_admin"},
                    {"title": "Production batches", "icon": "precision_manufacturing",
                     "link": reverse_lazy("admin:ops_productionbatch_changelist"), "permission": "ops.roles.is_admin"},
                    {"title": "Invoices", "icon": "receipt_long",
                     "link": reverse_lazy("admin:ops_invoice_changelist"), "permission": "ops.roles.is_admin"},
                    {"title": "Expenses", "icon": "payments",
                     "link": reverse_lazy("admin:ops_expense_changelist"), "permission": "ops.roles.is_admin"},
                    {"title": "Inventory settings", "icon": "tune",
                     "link": reverse_lazy("admin:ops_inventorysettings_changelist"), "permission": "ops.roles.is_admin"},
                ],
            },
            {
                "title": "Team",
                "collapsible": True,
                "items": [
                    {"title": "People & roles", "icon": "badge",
                     "link": reverse_lazy("admin:ops_staffprofile_changelist"), "permission": "ops.roles.is_admin"},
                    {"title": "Staff accounts", "icon": "person",
                     "link": reverse_lazy("admin:auth_user_changelist"), "permission": "ops.roles.is_admin"},
                    {"title": "Permission groups", "icon": "group",
                     "link": reverse_lazy("admin:auth_group_changelist"), "permission": "ops.roles.is_admin"},
                ],
            },
        ],
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
        "mail_admins": {"class": "django.utils.log.AdminEmailHandler", "level": "ERROR"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "paalvi": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console", "mail_admins"], "level": "ERROR", "propagate": False},
    },
}

# Thumbnails are generated once when a photo is saved (not on every page view).
IMAGEKIT_DEFAULT_CACHEFILE_STRATEGY = "imagekit.cachefiles.strategies.Optimistic"
