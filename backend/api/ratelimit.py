"""Tiny per-IP rate limiter (fixed 60-second window) using Django's cache (Redis or memory)."""

import time
from functools import wraps

from django.core.cache import cache
from ninja.errors import HttpError


def client_ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR", "")) or "unknown"


def rate_limit(name, per_minute):
    """Decorator: allow `per_minute` calls per visitor IP, then answer 429 with a friendly message."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            limit = per_minute() if callable(per_minute) else per_minute
            window = int(time.time() // 60)
            key = f"rl:{name}:{client_ip(request)}:{window}"
            cache.add(key, 0, timeout=70)
            try:
                count = cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=70)
                count = 1
            if count > limit:
                raise HttpError(429, "You're going a little fast — please wait a minute and try again.")
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
