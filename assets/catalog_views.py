"""
In-app catalog management — asset categories & types (Admin only).

Replaces the need to configure the catalog from the Django admin. Categories and
types use ``is_active`` as their soft-delete; a hard delete is only offered when
nothing depends on the record (the FKs are PROTECT, so a guarded delete is safe).
"""

from django.contrib import messages
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from config.permissions import admin_required

from .models import AssetCategory, AssetType
from .specs import (
    KNOWN_SPEC_FIELDS,
    compose_schema,
    slugify_spec_key,
    spec_label,
    split_schema,
)


# ── Catalog home ────────────────────────────────────────────────────────────────

@admin_required
def catalog_home(request):
    categories = AssetCategory.objects.order_by("name")
    types = (
        AssetType.objects.select_related("category")
        .annotate(item_count=Count("items"))
        .order_by("category__name", "name")
    )
    types_by_cat: dict[int, list] = {}
    for t in types:
        types_by_cat.setdefault(t.category_id, []).append(t)

    cat_rows = [{"category": c, "types": types_by_cat.get(c.pk, [])} for c in categories]

    return render(request, "assets/catalog/home.html", {
        "cat_rows":   cat_rows,
        "type_total": types.count(),
        "cat_total":  categories.count(),
    })


# ── Categories ──────────────────────────────────────────────────────────────────

@admin_required
def category_create(request):
    if request.method == "POST":
        error = _save_category(request, category=None)
        if error is None:
            messages.success(request, "Category created.")
            return redirect("assets:catalog_home")
        return render(request, "assets/catalog/category_form.html",
                      {"mode": "create", "post": request.POST, "form_error": error,
                       "category": AssetCategory()})
    return render(request, "assets/catalog/category_form.html",
                  {"mode": "create", "category": AssetCategory()})


@admin_required
def category_edit(request, pk):
    category = get_object_or_404(AssetCategory, pk=pk)
    if request.method == "POST":
        error = _save_category(request, category=category)
        if error is None:
            messages.success(request, f"Category '{category.name}' updated.")
            return redirect("assets:catalog_home")
        return render(request, "assets/catalog/category_form.html",
                      {"mode": "edit", "post": request.POST, "form_error": error,
                       "category": category})
    return render(request, "assets/catalog/category_form.html",
                  {"mode": "edit", "category": category})


@admin_required
@require_POST
def category_toggle(request, pk):
    category = get_object_or_404(AssetCategory, pk=pk)
    category.is_active = not category.is_active
    category.save(update_fields=["is_active", "updated_at"])
    messages.success(
        request,
        f"Category '{category.name}' {'activated' if category.is_active else 'deactivated'}.",
    )
    return redirect("assets:catalog_home")


@admin_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(AssetCategory, pk=pk)
    if category.asset_types.exists():
        messages.error(
            request,
            f"Cannot delete '{category.name}' — it still has asset types. "
            "Move or delete those first, or deactivate the category instead.",
        )
        return redirect("assets:catalog_home")
    name = category.name
    try:
        category.delete()
        messages.success(request, f"Category '{name}' deleted.")
    except ProtectedError:
        messages.error(request, f"Cannot delete '{name}' — it is still referenced.")
    return redirect("assets:catalog_home")


# ── Types ───────────────────────────────────────────────────────────────────────

@admin_required
def type_create(request):
    if request.method == "POST":
        error = _save_type(request, asset_type=None)
        if error is None:
            messages.success(request, "Asset type created.")
            return redirect("assets:catalog_home")
        return render(request, "assets/catalog/type_form.html",
                      _type_form_ctx(request, AssetType(), error))
    return render(request, "assets/catalog/type_form.html",
                  _type_form_ctx(request, AssetType(), None))


@admin_required
def type_edit(request, pk):
    asset_type = get_object_or_404(AssetType.objects.select_related("category"), pk=pk)
    if request.method == "POST":
        error = _save_type(request, asset_type=asset_type)
        if error is None:
            messages.success(request, f"Asset type '{asset_type.name}' updated.")
            return redirect("assets:catalog_home")
        return render(request, "assets/catalog/type_form.html",
                      _type_form_ctx(request, asset_type, error))
    return render(request, "assets/catalog/type_form.html",
                  _type_form_ctx(request, asset_type, None))


@admin_required
@require_POST
def type_toggle(request, pk):
    asset_type = get_object_or_404(AssetType, pk=pk)
    asset_type.is_active = not asset_type.is_active
    asset_type.save(update_fields=["is_active", "updated_at"])
    messages.success(
        request,
        f"Type '{asset_type.name}' {'activated' if asset_type.is_active else 'deactivated'}.",
    )
    return redirect("assets:catalog_home")


@admin_required
@require_POST
def type_delete(request, pk):
    asset_type = get_object_or_404(AssetType, pk=pk)
    if asset_type.items.exists():
        messages.error(
            request,
            f"Cannot delete '{asset_type.name}' — assets of this type exist. "
            "Deactivate it instead to hide it from new-asset forms.",
        )
        return redirect("assets:catalog_home")
    name = asset_type.name
    try:
        asset_type.delete()
        messages.success(request, f"Asset type '{name}' deleted.")
    except ProtectedError:
        messages.error(request, f"Cannot delete '{name}' — it is still referenced.")
    return redirect("assets:catalog_home")


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _save_category(request, category) -> str | None:
    data = request.POST
    name = data.get("name", "").strip()
    if not name:
        return "Category name is required."
    clash = AssetCategory.objects.filter(name__iexact=name)
    if category is not None:
        clash = clash.exclude(pk=category.pk)
    if clash.exists():
        return f"A category named '{name}' already exists."

    if category is None:
        category = AssetCategory()
    category.name = name
    category.name_bn = data.get("name_bn", "").strip()
    category.description = data.get("description", "").strip()
    category.is_active = data.get("is_active") == "on"
    category.save()
    return None


def _type_form_ctx(request, asset_type, error) -> dict:
    """Build the context for the type form, re-using POST data on validation errors."""
    categories = AssetCategory.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        checked_known = set(request.POST.getlist("known_specs"))
        seen, custom_keys = set(), []
        for raw in request.POST.getlist("custom_specs"):
            slug = slugify_spec_key(raw)
            if slug and slug not in seen:
                seen.add(slug)
                custom_keys.append(slug)
        selected_category = request.POST.get("category", "")
        has_components = request.POST.get("has_components") == "on"
        is_active = request.POST.get("is_active") == "on"
        name = request.POST.get("name", "")
        name_bn = request.POST.get("name_bn", "")
    else:
        known, custom_keys = split_schema(asset_type.spec_schema)
        checked_known = set(known)
        selected_category = str(asset_type.category_id or request.GET.get("category", ""))
        has_components = asset_type.has_components
        is_active = asset_type.is_active if asset_type.pk else True
        name = asset_type.name
        name_bn = asset_type.name_bn

    known_fields = [
        {"key": k, "label": lbl, "desc": desc, "checked": k in checked_known}
        for k, lbl, desc in KNOWN_SPEC_FIELDS
    ]
    custom_fields = [{"label": spec_label(k)} for k in custom_keys]

    return {
        "mode":             "edit" if asset_type.pk else "create",
        "asset_type":       asset_type,
        "categories":       categories,
        "selected_category": selected_category,
        "name":             name,
        "name_bn":          name_bn,
        "has_components":    has_components,
        "is_active":        is_active,
        "known_fields":     known_fields,
        "custom_fields":    custom_fields,
        "item_count":       asset_type.items.count() if asset_type.pk else 0,
        "form_error":       error,
    }


def _save_type(request, asset_type) -> str | None:
    data = request.POST
    name = data.get("name", "").strip()
    category_id = data.get("category", "").strip()

    if not name:
        return "Type name is required."
    if not category_id:
        return "Please choose a category."
    if not AssetCategory.objects.filter(pk=category_id).exists():
        return "Selected category does not exist."

    clash = AssetType.objects.filter(category_id=category_id, name__iexact=name)
    if asset_type is not None and asset_type.pk:
        clash = clash.exclude(pk=asset_type.pk)
    if clash.exists():
        return f"A type named '{name}' already exists in this category."

    schema = compose_schema(data.getlist("known_specs"), data.getlist("custom_specs"))

    if asset_type is None:
        asset_type = AssetType()
    asset_type.name = name
    asset_type.name_bn = data.get("name_bn", "").strip()
    asset_type.category_id = category_id
    asset_type.has_components = data.get("has_components") == "on"
    asset_type.is_active = data.get("is_active") == "on"
    asset_type.spec_schema = schema
    asset_type.save()
    return None
