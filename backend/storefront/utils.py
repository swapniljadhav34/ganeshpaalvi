"""
Small shared helpers used across Paalvi apps:
  - SingletonModel: models that should only ever have ONE row (brand settings…)
  - compress_image_field: turns big phone photos into light WebP files on save
  - contrast_ratio: WCAG colour contrast checker for the theme studio
"""

import io
import os

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db import models
from PIL import Image, ImageOps

BOOTSTRAP_CACHE_KEY = "paalvi:bootstrap:v2"


def clear_site_cache():
    """Forget cached homepage data so visitors see admin changes right away."""
    cache.delete(BOOTSTRAP_CACHE_KEY)


class SingletonModel(models.Model):
    """A model that always has exactly one row (id = 1)."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Deleting a singleton would break the site, so we simply ignore it.
        return (0, {})

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


def compress_image_field(field_file, max_side=2400, quality=82):
    """
    Convert an uploaded image to WebP and shrink it so the longest side is at most
    `max_side` pixels. Safe to call on every save — already-converted files are skipped.
    """
    if not field_file or not getattr(field_file, "name", ""):
        return
    name = field_file.name
    # Only process brand-new uploads (they are not yet committed to storage).
    if getattr(field_file, "_committed", True):
        return
    if name.lower().endswith((".svg", ".gif", ".ico")):
        return
    try:
        field_file.open()
        img = Image.open(field_file)
        img = ImageOps.exif_transpose(img)  # respect phone camera rotation
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
        img.thumbnail((max_side, max_side), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=quality, method=5)
        base = os.path.splitext(os.path.basename(name))[0]
        field_file.save(f"{base}.webp", ContentFile(buf.getvalue()), save=False)
    except Exception:
        # If anything goes wrong we keep the original file rather than lose it.
        pass


def _channel(c):
    c = c / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(hex_color):
    h = (hex_color or "#000000").lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    try:
        r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return 0
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(fg, bg):
    """WCAG contrast ratio between two hex colours (1 = none, 21 = black on white)."""
    a, b = _luminance(fg), _luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return round((hi + 0.05) / (lo + 0.05), 2)
