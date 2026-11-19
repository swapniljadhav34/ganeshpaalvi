"""Tiny per-IP rate limiter (fixed 60-second window) using Django's cache (Redis in production)."""

import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from ninja.errors import HttpError


def client_ip(request, *args, **kwargs):
    """The visitor's real IP, read ONLY from the header our own proxy sets (see CLIENT_IP_HEADER).

    Never trust the left-most X-Forwarded-For value: visitors can write anything there.
    """
    meta = request.META
    header = getattr(settings, "CLIENT_IP_HEADER", "HTTP_X_REAL_IP")
    if header == "XFF_RIGHTMOST":
        parts = [p.strip() for p in meta.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
        ip = parts[-1] if parts else ""
    elif header == "REMOTE_ADDR":
        ip = ""
    else:
        ip = meta.get(header, "").split(",")[0].strip()
    return ip or meta.get("REMOTE_ADDR", "") or "unknown"


def hit(name, request, limit, window_seconds=60):
    """Count one request; returns True if the caller is over the limit."""
    window = int(time.time() // window_seconds)
    key = f"rl:{name}:{client_ip(request)}:{window}"
    if cache.add(key, 1, timeout=window_seconds + 10):
        count = 1
    else:
        try:
            count = cache.incr(key)
        except ValueError:  # expired between add() and incr()
            cache.set(key, 1, timeout=window_seconds + 10)
            count = 1
    return count > limit


def rate_limit(name, per_minute):
    """Decorator: allow `per_minute` calls per visitor IP, then answer 429 with a friendly message."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            limit = per_minute() if callable(per_minute) else per_minute
            if hit(name, request, limit):
                raise HttpError(429, "You're going a little fast — please wait a minute and try again.")
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
