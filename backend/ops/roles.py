"""
Who may do what in Paalvi Studio.

Every staff API checks one of these permission names on the SERVER — hiding a tab in the
browser is only for convenience, never for security.

SUPER_ADMIN is always a Django superuser (and only superusers may open /admin/ settings
and manage staff). Every other role is an employee who can only use the Studio tabs below.
"""

from django.db import models


class Role(models.TextChoices):
    SUPER_ADMIN = "SUPER_ADMIN", "Super admin (owner)"
    ACCOUNTANT = "ACCOUNTANT", "Accountant"
    INVENTORY_MANAGER = "INVENTORY_MANAGER", "Inventory manager"
    PRODUCTION_MANAGER = "PRODUCTION_MANAGER", "Production manager"
    EMPLOYEE_OPS = "EMPLOYEE_OPS", "Operations employee"
    EMPLOYEE_CATALOG = "EMPLOYEE_CATALOG", "Catalog & media employee"
    WHOLESALE_MANAGER = "WHOLESALE_MANAGER", "Wholesale manager"


PERMISSIONS = {
    "inventory.view": "See stock levels and alerts",
    "inventory.adjust": "Add or remove stock (a reason is always required)",
    "inventory.batches": "Edit batch numbers and expiry dates",
    "inventory.configure": "Set low-stock thresholds, reorder points and expiry warnings",
    "inventory.audit": "See the full stock movement log",
    "inventory.export": "Export stock to CSV",
    "production.view": "See production batches",
    "production.update": "Move assigned batches through stages and log output",
    "production.manage": "Create, assign and update any batch",
    "accounting.view": "See invoices, payments, expenses and reports",
    "accounting.edit": "Create invoices, record payments and log expenses",
    "accounting.export": "Export accounting data to CSV",
    "leads.view": "See enquiries and orders",
    "leads.update": "Update enquiry status and notes",
    "catalog.media": "Upload 3D models and choose the 3D hero",
    "analytics.view": "See website traffic",
    "staff.manage": "Manage staff accounts and site settings",
}

ROLE_PERMISSIONS = {
    Role.SUPER_ADMIN: set(PERMISSIONS),
    Role.ACCOUNTANT: {"accounting.view", "accounting.edit", "accounting.export"},
    Role.INVENTORY_MANAGER: {"inventory.view", "inventory.adjust", "inventory.batches", "production.view"},
    Role.PRODUCTION_MANAGER: {"production.view", "production.update", "production.manage", "inventory.view"},
    Role.EMPLOYEE_OPS: {"inventory.view", "inventory.adjust", "production.view", "production.update",
                        "leads.view", "leads.update"},
    Role.EMPLOYEE_CATALOG: {"catalog.media", "inventory.view"},
    Role.WHOLESALE_MANAGER: {"leads.view", "leads.update", "inventory.view"},
}

# Studio tabs and the permission that unlocks each one (order = sidebar order).
TABS = [
    ("inventory", "Inventory", "inventory.view"),
    ("production", "Production", "production.view"),
    ("inquiries", "Orders & enquiries", "leads.view"),
    ("accounting", "Accounting", "accounting.view"),
    ("catalog", "Catalog & 3D", "catalog.media"),
    ("traffic", "Traffic", "analytics.view"),
    ("team", "Team & settings", "staff.manage"),
]


def user_role(user):
    """The user's effective role, or None if they have no Studio access."""
    if not user or not getattr(user, "is_authenticated", False) or not user.is_active:
        return None
    if user.is_superuser:
        return Role.SUPER_ADMIN
    profile = getattr(user, "staff_profile", None)
    if profile is None or not profile.is_active:
        return None
    return Role(profile.role)


def user_permissions(user):
    role = user_role(user)
    return set(ROLE_PERMISSIONS.get(role, set())) if role else set()


def has_perm(user, perm):
    return perm in user_permissions(user)


def user_tabs(user):
    perms = user_permissions(user)
    return [{"key": k, "label": label} for k, label, p in TABS if p in perms]
