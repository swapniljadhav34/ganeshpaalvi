"""System tools for the Admin: health, clear cache, one-click recovery, factory reset (all without a restart)."""

import logging

from ninja import Schema
from ninja.errors import HttpError
from pydantic import Field

from .api import staff_router
from .maintenance import clear_caches, health, recover, reset_site
from .permissions import needs

log = logging.getLogger("paalvi")


@staff_router.get("/system/health")
@needs("system.maintain")
def system_health(request):
    return health()


@staff_router.post("/system/clear-cache")
@needs("system.maintain")
def system_clear_cache(request):
    clear_caches()
    log.warning("Cache cleared by %s", request.auth.get_username())
    return {"ok": True}


@staff_router.post("/system/recover")
@needs("system.maintain")
def system_recover(request):
    log.warning("Recovery run by %s", request.auth.get_username())
    return recover()


class ResetIn(Schema):
    confirm: str = Field(..., max_length=20)
    password: str = Field(..., min_length=1, max_length=256)
    load_sample: bool = False


@staff_router.post("/system/reset")
@needs("system.maintain")
def system_reset(request, payload: ResetIn):
    # Two safeguards on top of the Admin-only permission: type RESET, and re-enter your password.
    if payload.confirm.strip() != "RESET":
        raise HttpError(400, "Type RESET in capitals to confirm.")
    if not request.auth.check_password(payload.password):
        raise HttpError(403, "That password isn't right.")
    log.warning("Site reset by %s (sample=%s)", request.auth.get_username(), payload.load_sample)
    out = reset_site(load_sample=payload.load_sample)
    return {"ok": True, "backup": out["backup"].rsplit("/", 1)[-1].rsplit("\\", 1)[-1], "sample_loaded": out["sample_loaded"]}
