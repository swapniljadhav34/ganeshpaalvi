"""
Who may do what — one permission matrix for the whole system.

  • Every Studio API checks a permission name on the SERVER (hiding a tab is only convenience).
  • The Designer workspace (Django admin) reads the SAME matrix through ops.backends, so
    "site.design" opens the website-design screens and "catalog.edit" the product screens.
  • Roles and their permissions live in the database (ops.RoleDefinition). The Admin edits
    them in Studio → Team → Roles & permissions, can create new roles, and can grant extra
    permissions to one person (to cover someone else's job) without changing their role.

Two roles are fixed:
  • SUPER_ADMIN ("Admin") always has every permission. It can't be reduced, so the owner can
    never lock themselves out.
  • ADMIN_ONLY permissions (staff accounts and system maintenance) are never granted to other
    roles — anyone holding them could promote themselves to Admin.
"""

from dataclasses import dataclass, field

from django.core.cache import cache
from django.db import models


class Role(models.TextChoices):
    """Built-in roles (keys are stored in the database; the Admin can add more)."""

    SUPER_ADMIN = "SUPER_ADMIN", "Admin"
    DESIGNER = "DESIGNER", "Designer"
    ACCOUNTANT = "ACCOUNTANT", "Accountant"
    INVENTORY_MANAGER = "INVENTORY_MANAGER", "Inventory manager"
    PRODUCTION_MANAGER = "PRODUCTION_MANAGER", "Production manager"
    EMPLOYEE_OPS = "EMPLOYEE_OPS", "Operations employee"
    EMPLOYEE_CATALOG = "EMPLOYEE_CATALOG", "Catalog & media employee"
    WHOLESALE_MANAGER = "WHOLESALE_MANAGER", "Wholesale manager"
    MARKETING = "MARKETING", "Marketing team"
    DISTRIBUTION = "DISTRIBUTION", "Distribution team"
    WAREHOUSE = "WAREHOUSE", "Warehouse worker"
    VENDOR = "VENDOR", "Supply-chain vendor"


# Grouped for the permission matrix screen: (group, [(permission, description)]).
PERMISSION_GROUPS = [
    ("Website", [
        ("site.design", "Design the website: homepage builder, sections, hero, menus, colours, brand text, translations"),
    ]),
    ("Products", [
        ("catalog.edit", "Add and edit products, categories, photos and prices"),
        ("catalog.delete", "Delete products and categories permanently"),
        ("catalog.media", "Upload 3D models and choose the 3D hero"),
    ]),
    ("Inventory", [
        ("inventory.view", "See stock levels and alerts"),
        ("inventory.adjust", "Add or remove stock (a reason is always required)"),
        ("inventory.reset", "Reset a product's stock to zero in one click"),
        ("inventory.batches", "Edit batch numbers and expiry dates"),
        ("inventory.configure", "Set low-stock thresholds, reorder points and expiry warnings"),
        ("inventory.audit", "See the full stock movement log"),
        ("inventory.export", "Export stock to CSV"),
    ]),
    ("Production", [
        ("production.view", "See production batches"),
        ("production.update", "Move assigned batches through stages and log output"),
        ("production.manage", "Create, assign and update any batch"),
    ]),
    ("Orders", [
        ("orders.view", "See the order book and print receipts"),
        ("orders.create", "Log offline orders (phone, field, walk-in, WhatsApp)"),
        ("orders.update", "Change order status (confirm, pack, dispatch, deliver, cancel)"),
        ("leads.view", "See website enquiries"),
        ("leads.update", "Update enquiry status and notes"),
    ]),
    ("Accounts", [
        ("accounting.view", "See invoices, payments, expenses and reports"),
        ("accounting.edit", "Create invoices, record payments and log expenses"),
        ("accounting.export", "Export accounting data to CSV"),
    ]),
    ("Insights", [
        ("analytics.view", "See website traffic"),
        ("directory.view", "See the people & vendor directory"),
    ]),
    ("Admin only", [
        ("staff.manage", "Manage accounts, roles and permissions"),
        ("system.maintain", "Clear cache, run recovery and reset the site"),
    ]),
]
PERMISSIONS = {p: d for _, items in PERMISSION_GROUPS for p, d in items}
ADMIN_ONLY = {"staff.manage", "system.maintain"}
GRANTABLE = set(PERMISSIONS) - ADMIN_ONLY

# Permissions that open the Designer workspace (the Django admin screens).
DESIGNER_PERMS = {"site.design", "catalog.edit", "catalog.delete"}

DEFAULT_ROLE_PERMISSIONS = {
    Role.SUPER_ADMIN: set(PERMISSIONS),
    Role.DESIGNER: {"site.design", "catalog.edit", "catalog.media"},
    Role.ACCOUNTANT: {"accounting.view", "accounting.edit", "accounting.export", "orders.view"},
    Role.INVENTORY_MANAGER: {"inventory.view", "inventory.adjust", "inventory.reset", "inventory.batches", "production.view", "orders.view"},
    Role.PRODUCTION_MANAGER: {"production.view", "production.update", "production.manage", "inventory.view"},
    Role.EMPLOYEE_OPS: {"inventory.view", "inventory.adjust", "production.view", "production.update",
                        "leads.view", "leads.update", "orders.view", "orders.update"},
    Role.EMPLOYEE_CATALOG: {"catalog.media", "catalog.edit", "inventory.view"},
    Role.WHOLESALE_MANAGER: {"leads.view", "leads.update", "inventory.view", "orders.view", "orders.create", "orders.update"},
    Role.MARKETING: {"orders.view", "orders.create", "leads.view", "leads.update", "analytics.view", "inventory.view"},
    Role.DISTRIBUTION: {"orders.view", "orders.create", "orders.update", "inventory.view", "directory.view"},
    Role.WAREHOUSE: {"orders.view", "orders.update", "inventory.view", "inventory.adjust"},
    Role.VENDOR: {"production.view"},
}

DEFAULT_ROLE_DESCRIPTIONS = {
    Role.SUPER_ADMIN: "Master control of everything: accounts, roles, settings and maintenance.",
    Role.DESIGNER: "Designs the website and edits products in the Designer workspace.",
    Role.MARKETING: "Logs field and phone orders, follows up enquiries.",
    Role.DISTRIBUTION: "Logs orders and moves them through dispatch and delivery.",
    Role.WAREHOUSE: "Packs and dispatches orders and records stock.",
    Role.VENDOR: "External supplier — sees production batches only.",
}

# Studio tabs and the permission that unlocks each one (order = sidebar order).
TABS = [
    ("orders", "Order book", "orders.view"),
    ("inventory", "Inventory", "inventory.view"),
    ("production", "Production", "production.view"),
    ("inquiries", "Enquiries", "leads.view"),
    ("accounting", "Accounting", "accounting.view"),
    ("catalog", "Products & 3D", "catalog.media"),
    ("traffic", "Traffic", "analytics.view"),
    ("directory", "Directory", "directory.view"),
    ("team", "Team & roles", "staff.manage"),
    ("system", "System", "system.maintain"),
]


@dataclass(frozen=True)
class RoleInfo:
    key: str
    label: str
    permissions: frozenset = field(default_factory=frozenset)

    # Old code used Role enum members — keep `.value` working.
    @property
    def value(self):
        return self.key

    @property
    def is_admin(self):
        return self.key == Role.SUPER_ADMIN


_CACHE_KEY = "ops:role-matrix:v1"


def role_matrix():
    """{key: RoleInfo} for every role, cached until a role is edited."""
    data = cache.get(_CACHE_KEY)
    if data is None:
        from .models import RoleDefinition  # avoid an import cycle

        data = {r.key: (r.label, sorted(r.permissions or [])) for r in RoleDefinition.objects.all()}
        cache.set(_CACHE_KEY, data, 3600)
    # Admin-only permissions are stripped from every other role, whatever the database says.
    out = {k: RoleInfo(k, label, frozenset(perms) & GRANTABLE) for k, (label, perms) in data.items()}
    for r in Role:  # built-ins always exist, even before the data migration runs
        out.setdefault(r.value, RoleInfo(r.value, r.label, frozenset(DEFAULT_ROLE_PERMISSIONS[r])))
    # The Admin always has everything, whatever the database says.
    out[Role.SUPER_ADMIN] = RoleInfo(Role.SUPER_ADMIN, out[Role.SUPER_ADMIN].label, frozenset(PERMISSIONS))
    return out


def forget_role_matrix():
    cache.delete(_CACHE_KEY)


def role_info(key):
    return role_matrix().get(key)


def user_role(user):
    """The user's effective role (RoleInfo), or None if they have no Studio access."""
    if not user or not getattr(user, "is_authenticated", False) or not user.is_active:
        return None
    if user.is_superuser:
        return role_info(Role.SUPER_ADMIN)
    profile = getattr(user, "staff_profile", None)
    if profile is None or not profile.is_active:
        return None
    return role_info(profile.role)


def user_permissions(user):
    role = user_role(user)
    if not role:
        return set()
    perms = set(role.permissions)
    profile = getattr(user, "staff_profile", None)
    if profile is not None and not role.is_admin:
        perms |= set(profile.extra_permissions or []) & GRANTABLE
    return perms


def has_perm(user, perm):
    return perm in user_permissions(user)


def user_tabs(user):
    perms = user_permissions(user)
    return [{"key": k, "label": label} for k, label, p in TABS if p in perms]


def wants_designer_access(perms):
    return bool(set(perms) & DESIGNER_PERMS)


# ---- Sidebar permission callbacks for the Designer workspace (settings.UNFOLD) ----
def _req_has(perm):
    return lambda request: has_perm(request.user, perm)


can_design = _req_has("site.design")
can_edit_catalog = _req_has("catalog.edit")
can_see_leads = _req_has("leads.view")


def is_admin(request):
    return bool(request.user.is_active and request.user.is_superuser)
