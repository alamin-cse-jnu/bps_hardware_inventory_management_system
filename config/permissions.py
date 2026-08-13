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

def _group_names(user) -> set[str]:
    """
    The user's group names, fetched once per user instance.

    A single request hits these predicates repeatedly — the access decorator,
    then `role_context` for the template flags — and each `.filter().exists()`
    was its own round trip to Postgres. `request.user` is one object for the
    life of the request, so memoising on it collapses all of them into one
    query.
    """
    names = getattr(user, "_cached_group_names", None)
    if names is None:
        names = set(user.groups.values_list("name", flat=True))
        user._cached_group_names = names
    return names


def is_admin(user) -> bool:
    return user.is_superuser or GROUP_ADMIN in _group_names(user)


def is_it_officer_or_above(user) -> bool:
    return is_admin(user) or GROUP_IT_OFFICER in _group_names(user)


def is_viewer_or_above(user) -> bool:
    return is_it_officer_or_above(user) or GROUP_VIEWER in _group_names(user)


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
