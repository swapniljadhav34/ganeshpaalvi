"""
Paalvi — Django settings.

Everything that changes between your laptop and the live server is read from
environment variables (see `.env.example`). Sensible local defaults mean you can
run the project with zero configuration.
"""

import os
from pathlib import Path

import dj_database_url
from django.templatetags.static import static
from django.urls import reverse_lazy
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    """Read 'true/false/1/0/yes/no' style environment variables."""
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    """Read comma-separated environment variables into a clean list."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# --- Core -------------------------------------------------------------------
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,paalvi.in,www.paalvi.in,api.paalvi.in")
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS", "https://paalvi.in,https://www.paalvi.in,https://api.paalvi.in"
)

# Public site address — used for sitemap links, share links and "View on site".
SITE_URL = os.getenv("SITE_URL", "http://localhost:5173" if DEBUG else "https://paalvi.in").rstrip("/")

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
    # Paalvi apps
    "storefront",
    "catalog",
    "leads",
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
]

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

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/admin/"

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

# Built React app (frontend/dist). When present, Django can serve it with
# server-rendered share previews for WhatsApp / Facebook (see api/spa.py).
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", BASE_DIR.parent / "frontend" / "dist"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000
FILE_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024

# --- CORS: only paalvi.in may call the API from a browser --------------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "https://paalvi.in,https://www.paalvi.in")
if DEBUG:
    CORS_ALLOWED_ORIGINS += ["http://localhost:5173", "http://127.0.0.1:5173"]

# --- Security for production ------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True

# --- Email (new-lead notifications) ----------------------------------------
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Paalvi <no-reply@paalvi.in>")
LEAD_NOTIFY_EMAILS = env_list("LEAD_NOTIFY_EMAILS", "")

# --- AI concierge (any OpenAI-compatible provider) ---------------------------
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.groq.com/openai/v1")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "llama-3.1-8b-instant")
AI_TIMEOUT_SECONDS = float(os.getenv("AI_TIMEOUT_SECONDS", "20"))

# --- Rate limits (requests per minute per visitor IP) ------------------------
RATE_LIMIT_AI_PER_MIN = int(os.getenv("RATE_LIMIT_AI_PER_MIN", "15"))
RATE_LIMIT_INQUIRY_PER_MIN = int(os.getenv("RATE_LIMIT_INQUIRY_PER_MIN", "5"))

# --- Admin look & feel (django-unfold) --------------------------------------
UNFOLD = {
    "SITE_TITLE": "Paalvi Studio",
    "SITE_HEADER": "Paalvi Studio",
    "SITE_SUBHEADER": "Manage your showroom",
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
                     "link": reverse_lazy("admin:storefront_brandsettings_changelist")},
                ],
            },
            {
                "title": "Theme & Festival Studio",
                "collapsible": True,
                "items": [
                    {"title": "Active theme & schedule", "icon": "palette",
                     "link": reverse_lazy("admin:storefront_activetheme_changelist")},
                    {"title": "Theme presets", "icon": "format_paint",
                     "link": reverse_lazy("admin:storefront_themepreset_changelist")},
                ],
            },
            {
                "title": "Site Design Studio",
                "collapsible": True,
                "items": [
                    {"title": "Shapes, motion, header & footer", "icon": "animation",
                     "link": reverse_lazy("admin:storefront_sitedesign_changelist")},
                    {"title": "Header menu links", "icon": "menu",
                     "link": reverse_lazy("admin:storefront_navlink_changelist")},
                    {"title": "Footer columns & links", "icon": "view_column",
                     "link": reverse_lazy("admin:storefront_footercolumn_changelist")},
                ],
            },
            {
                "title": "Homepage Builder",
                "collapsible": True,
                "items": [
                    {"title": "Hero slides", "icon": "movie",
                     "link": reverse_lazy("admin:storefront_heroslide_changelist")},
                    {"title": "Page sections", "icon": "view_agenda",
                     "link": reverse_lazy("admin:storefront_pagesection_changelist")},
                ],
            },
            {
                "title": "Products",
                "collapsible": True,
                "items": [
                    {"title": "Products", "icon": "inventory_2",
                     "link": reverse_lazy("admin:catalog_product_changelist")},
                    {"title": "Categories", "icon": "category",
                     "link": reverse_lazy("admin:catalog_category_changelist")},
                    {"title": "Ingredients", "icon": "eco",
                     "link": reverse_lazy("admin:catalog_ingredient_changelist")},
                    {"title": "Badges (free-from, vegan…)", "icon": "verified",
                     "link": reverse_lazy("admin:catalog_badge_changelist")},
                    {"title": "Variants (all products)", "icon": "tune",
                     "link": reverse_lazy("admin:catalog_productvariant_changelist")},
                    {"title": "Pack sizes (all products)", "icon": "package_2",
                     "link": reverse_lazy("admin:catalog_packageoption_changelist")},
                ],
            },
            {
                "title": "Leads & Enquiries",
                "collapsible": True,
                "items": [
                    {"title": "All enquiries", "icon": "contact_phone",
                     "link": reverse_lazy("admin:leads_leadinquiry_changelist")},
                ],
            },
            {
                "title": "AI Concierge",
                "collapsible": True,
                "items": [
                    {"title": "Care Guide settings", "icon": "smart_toy",
                     "link": reverse_lazy("admin:storefront_aiassistantconfig_changelist")},
                ],
            },
            {
                "title": "Team",
                "collapsible": True,
                "items": [
                    {"title": "Staff accounts", "icon": "person",
                     "link": reverse_lazy("admin:auth_user_changelist")},
                    {"title": "Permission groups", "icon": "group",
                     "link": reverse_lazy("admin:auth_group_changelist")},
                ],
            },
        ],
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO" if not DEBUG else "WARNING"},
    "loggers": {"paalvi": {"handlers": ["console"], "level": "INFO", "propagate": False}},
}

# Thumbnails are generated once when a photo is saved (not on every page view).
IMAGEKIT_DEFAULT_CACHEFILE_STRATEGY = "imagekit.cachefiles.strategies.Optimistic"
