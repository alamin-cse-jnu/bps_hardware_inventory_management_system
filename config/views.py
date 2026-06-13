from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .permissions import GROUP_ADMIN, GROUP_IT_OFFICER, GROUP_VIEWER, admin_required

User = get_user_model()

_ALL_GROUPS = [GROUP_ADMIN, GROUP_IT_OFFICER, GROUP_VIEWER]


def _user_role(user) -> str:
    for g in _ALL_GROUPS:
        if user.groups.filter(name=g).exists():
            return g
    return ""


@admin_required
def user_list(request):
    users = (
        User.objects.prefetch_related("groups")
        .order_by("is_active", "username")
        .exclude(is_superuser=True)
    )
    rows = [{"user": u, "role": _user_role(u)} for u in users]
    return render(request, "users/user_list.html", {"rows": rows})


@admin_required
def user_create(request):
    if request.method == "POST":
        error = _save_user(request, user=None)
        if error is None:
            messages.success(request, "User created successfully.")
            return redirect("config:user_list")
        return render(request, "users/user_form.html", {
            "form_error": error,
            "post": request.POST,
            "edit_user": User(),
            "groups": _ALL_GROUPS,
            "mode": "create",
        })

    return render(request, "users/user_form.html", {
        "edit_user": User(),
        "groups": _ALL_GROUPS,
        "mode": "create",
    })


@admin_required
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk, is_superuser=False)
    if request.method == "POST":
        error = _save_user(request, user=user)
        if error is None:
            messages.success(request, f"User '{user.username}' updated.")
            return redirect("config:user_list")
        return render(request, "users/user_form.html", {
            "form_error": error,
            "post": request.POST,
            "edit_user": user,
            "current_role": _user_role(user),
            "groups": _ALL_GROUPS,
            "mode": "edit",
        })

    return render(request, "users/user_form.html", {
        "edit_user": user,
        "current_role": _user_role(user),
        "groups": _ALL_GROUPS,
        "mode": "edit",
    })


@admin_required
@require_POST
def user_toggle_active(request, pk):
    user = get_object_or_404(User, pk=pk, is_superuser=False)
    if user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("config:user_list")
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    state = "activated" if user.is_active else "deactivated"
    from audit.services import record as audit_record
    audit_record("UPDATE", user, changes={"is_active": [not user.is_active, user.is_active]}, note=state.title())
    messages.success(request, f"User '{user.username}' {state}.")
    return redirect("config:user_list")


# ── helpers ───────────────────────────────────────────────────────────────────

def _save_user(request, user) -> str | None:
    """Create or update a user. Returns error string or None on success."""
    from audit.services import record as audit_record

    data = request.POST
    username = data.get("username", "").strip()
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    email = data.get("email", "").strip()
    role = data.get("role", "").strip()
    password = data.get("password", "").strip()
    confirm = data.get("confirm_password", "").strip()

    is_create = user is None
    before = None if is_create else {
        "first_name": user.first_name, "last_name": user.last_name,
        "email": user.email, "is_active": user.is_active, "role": _user_role(user),
    }

    if user is None:
        if not username:
            return "Username is required."
        if User.objects.filter(username=username).exists():
            return f"Username '{username}' is already taken."
        if not password:
            return "Password is required for new users."

    if password:
        if len(password) < 8:
            return "Password must be at least 8 characters."
        if password != confirm:
            return "Passwords do not match."

    if user is None:
        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
        )
    else:
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        if password:
            user.set_password(password)
        user.save()

    user.groups.clear()
    if role in _ALL_GROUPS:
        grp = Group.objects.get(name=role)
        user.groups.add(grp)

    # Audit (User isn't auto-tracked by signals — role is an m2m relation)
    if is_create:
        audit_record("CREATE", user, changes={
            "username": [None, user.username],
            "role": [None, role or "—"],
            "is_active": [None, user.is_active],
        })
    else:
        after = {
            "first_name": first_name, "last_name": last_name,
            "email": email, "is_active": user.is_active, "role": role,
        }
        changes = {k: [before[k], after[k]] for k in after if before.get(k) != after[k]}
        if password:
            changes["password"] = ["••••", "changed"]
        if changes:
            audit_record("UPDATE", user, changes=changes)

    return None
