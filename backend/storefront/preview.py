"""
Admin live preview.

The admin shows the real website inside a frame. A signed, expiring token lets that frame
load a hero slide or section even while it is hidden or scheduled — without making hidden
content public. While the owner edits, the admin sends unsaved field values to the frame,
so changes appear instantly.
"""

from django.conf import settings
from django.core import signing
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.utils.safestring import mark_safe

from . import design as D

SALT = "paalvi-preview"
MAX_AGE = 60 * 60 * 12  # 12 hours


def make_token(kind, pk=None):
    return signing.dumps({"k": kind, "id": pk}, salt=SALT)


def read_token(token):
    """Returns (kind, pk) or raises signing.BadSignature."""
    data = signing.loads(token, salt=SALT, max_age=MAX_AGE)
    return data["k"], data.get("id")


def preview_panel(kind, obj=None, height=620):
    """The preview frame + device switcher + replay button, rendered as a readonly admin field."""
    token = make_token(kind, obj.pk if obj and obj.pk else None)
    return mark_safe(render_to_string("admin/storefront/live_preview.html", {
        "src": f"{settings.SITE_URL}/__preview?kind={kind}&token={token}",
        "site_origin": settings.SITE_URL,
        "height": height,
        "kind": kind,
        "registry": D.admin_registry(),
        "script": static("admin/paalvi-preview.js"),
    }))
