"""
Connects the Designer workspace (Django admin) to the Studio permission matrix.

Django asks "may this user change storefront.PageSection?" as `user.has_perm("storefront.change_pagesection")`.
This backend answers from ops.roles instead of Django's per-model permission tables, so there is
ONE place to grant access (Studio → Team & roles) instead of two systems that drift apart.

  storefront.*                        → site.design
  catalog.view / add / change         → catalog.edit   (site.design may view, to pick products in sections)
  catalog.delete                      → catalog.delete
  leads.view / change                 → leads.view / leads.update
  everything else (ops, auth, …)      → Admin only (Django's normal superuser rule)
"""

from .roles import user_permissions


def _needed(app_label, action):
    if app_label == "storefront":
        return {"site.design"}
    if app_label == "catalog":
        if action == "delete":
            return {"catalog.delete"}
        if action == "view":
            return {"catalog.edit", "site.design", "catalog.delete"}
        return {"catalog.edit"}
    if app_label == "leads":
        return {"leads.view"} if action == "view" else {"leads.update"}
    return None


class RolePermissionBackend:
    def authenticate(self, request, **credentials):
        return None  # never logs anyone in — ModelBackend/axes do that

    def _perms(self, user_obj):
        if not user_obj.is_active or user_obj.is_anonymous:
            return set()
        cached = getattr(user_obj, "_ops_perm_cache", None)
        if cached is None:
            cached = user_permissions(user_obj)
            user_obj._ops_perm_cache = cached
        return cached

    def has_perm(self, user_obj, perm, obj=None):
        try:
            app_label, codename = perm.split(".", 1)
        except ValueError:
            return False
        need = _needed(app_label, codename.split("_", 1)[0])
        return bool(need and need & self._perms(user_obj))

    def has_module_perms(self, user_obj, app_label):
        return any(self.has_perm(user_obj, f"{app_label}.{a}_x") for a in ("view", "change", "add", "delete"))

    def get_user_permissions(self, user_obj, obj=None):
        return set()

    def get_group_permissions(self, user_obj, obj=None):
        return set()

    def get_all_permissions(self, user_obj, obj=None):
        return set()
