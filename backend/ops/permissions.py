"""
Server-side permission checks for the Studio API.

    @router.get("/inventory/items")
    @needs("inventory.view")
    def items(request): ...

The router uses session authentication with CSRF protection (Ninja's django_auth), so a
request must come from a logged-in staff browser session. `needs` then checks the role.
"""

from functools import wraps

from ninja.errors import HttpError

from .roles import has_perm, user_role


def needs(*perms):
    """Allow the request only if the user has EVERY listed permission."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            user = request.auth
            if user_role(user) is None:
                raise HttpError(403, "This account doesn't have Studio access.")
            if not all(has_perm(user, p) for p in perms):
                raise HttpError(403, "You don't have permission to do this. Ask the owner if you need access.")
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
