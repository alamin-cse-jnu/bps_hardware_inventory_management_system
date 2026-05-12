"""
RBAC helpers for Parliament IT Inventory.

Three roles (Django Groups):
  Admin      — full access including catalog management and user admin
  IT Officer — operational: assign, transfer, lifecycle events, sync
  Viewer     — read-only: browse assets, holders, history; download reports

Superusers bypass all checks.
Users with no group assigned get a 403 on any view that needs a role check.
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

GROUP_ADMIN = "Admin"
GROUP_IT_OFFICER = "IT Officer"
GROUP_VIEWER = "Viewer"


# ── Predicate helpers ─────────────────────────────────────────────────────────

def is_admin(user) -> bool:
    return user.is_superuser or user.groups.filter(name=GROUP_ADMIN).exists()


def is_it_officer_or_above(user) -> bool:
    return is_admin(user) or user.groups.filter(name=GROUP_IT_OFFICER).exists()


def is_viewer_or_above(user) -> bool:
    return is_it_officer_or_above(user) or user.groups.filter(name=GROUP_VIEWER).exists()


# ── Decorators ────────────────────────────────────────────────────────────────

def _make_decorator(predicate):
    """Return a view decorator that enforces `predicate(user)`."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not predicate(request.user):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# Apply to any view that any authenticated role should reach (read-only pages).
viewer_required = _make_decorator(is_viewer_or_above)

# Apply to views that modify data (assign, transfer, lifecycle, sync).
it_officer_required = _make_decorator(is_it_officer_or_above)

# Apply to administration-only views (user management, catalog changes).
admin_required = _make_decorator(is_admin)


# ── Template context helper ───────────────────────────────────────────────────

def role_context(user) -> dict:
    """
    Inject into template context so templates can show/hide UI elements
    based on the current user's role without extra queries per element.
    """
    return {
        "user_is_admin": is_admin(user),
        "user_is_it_officer": is_it_officer_or_above(user),
        "user_is_viewer": is_viewer_or_above(user),
    }
