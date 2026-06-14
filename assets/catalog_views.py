"""
In-app catalog management — asset categories & types (Admin only).

Replaces the need to configure the catalog from the Django admin. Categories and
types use ``is_active`` as their soft-delete; a hard delete is only offered when
nothing depends on the record (the FKs are PROTECT, so a guarded delete is safe).
"""

from django.contrib import messages
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from config.permissions import admin_required

from .models import AssetCategory, AssetItem, AssetModelName, AssetType, Brand, SpecChoice, Vendor
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


# ── Dropdowns home (Brands / Model Names / Vendors) ─────────────────────────

@admin_required
def dropdowns_home(request):
    # brand/model_name/supplier are CharFields on AssetItem, not FKs,
    # so count by matching string values rather than reverse relation.
    brand_counts = dict(
        AssetItem.objects.filter(is_deleted=False)
        .values_list("brand")
        .annotate(c=Count("id"))
        .values_list("brand", "c")
    )
    model_counts = dict(
        AssetItem.objects.filter(is_deleted=False)
        .values_list("model_name")
        .annotate(c=Count("id"))
        .values_list("model_name", "c")
    )
    vendor_counts = dict(
        AssetItem.objects.filter(is_deleted=False)
        .values_list("supplier")
        .annotate(c=Count("id"))
        .values_list("supplier", "c")
    )

    brands = list(Brand.objects.order_by("name"))
    for b in brands:
        b.asset_count = brand_counts.get(b.name, 0)

    model_names = list(AssetModelName.objects.order_by("name"))
    for m in model_names:
        m.asset_count = model_counts.get(m.name, 0)

    vendors = list(Vendor.objects.order_by("name"))
    for v in vendors:
        v.asset_count = vendor_counts.get(v.name, 0)

    return render(request, "assets/catalog/dropdowns_home.html", {
        "brands": brands,
        "model_names": model_names,
        "vendors": vendors,
    })


# ── Brand CRUD ───────────────────────────────────────────────────────────────

@admin_required
def brand_create(request):
    if request.method == "POST":
        error = _save_brand(request, obj=None)
        if error is None:
            messages.success(request, "Brand added.")
            return redirect("assets:dropdowns_home")
        return render(request, "assets/catalog/brand_form.html",
                      {"mode": "create", "obj": Brand(), "post": request.POST, "form_error": error})
    return render(request, "assets/catalog/brand_form.html", {"mode": "create", "obj": Brand()})


@admin_required
def brand_edit(request, pk):
    obj = get_object_or_404(Brand, pk=pk)
    if request.method == "POST":
        error = _save_brand(request, obj=obj)
        if error is None:
            messages.success(request, f"Brand '{obj.name}' updated.")
            return redirect("assets:dropdowns_home")
        return render(request, "assets/catalog/brand_form.html",
                      {"mode": "edit", "obj": obj, "post": request.POST, "form_error": error})
    return render(request, "assets/catalog/brand_form.html", {"mode": "edit", "obj": obj})


@admin_required
@require_POST
def brand_toggle(request, pk):
    obj = get_object_or_404(Brand, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active", "updated_at"])
    messages.success(request, f"Brand '{obj.name}' {'activated' if obj.is_active else 'deactivated'}.")
    return redirect("assets:dropdowns_home")


@admin_required
@require_POST
def brand_delete(request, pk):
    obj = get_object_or_404(Brand, pk=pk)
    if AssetItem.objects.filter(brand=obj.name, is_deleted=False).exists():
        messages.error(request, f"Cannot delete '{obj.name}' — assets reference it. Deactivate instead.")
        return redirect("assets:dropdowns_home")
    name = obj.name
    obj.delete()
    messages.success(request, f"Brand '{name}' deleted.")
    return redirect("assets:dropdowns_home")


# ── Model Name CRUD ──────────────────────────────────────────────────────────

@admin_required
def model_name_create(request):
    if request.method == "POST":
        error = _save_model_name(request, obj=None)
        if error is None:
            messages.success(request, "Model name added.")
            return redirect("assets:dropdowns_home")
        return render(request, "assets/catalog/model_name_form.html",
                      {"mode": "create", "obj": AssetModelName(), "post": request.POST, "form_error": error})
    return render(request, "assets/catalog/model_name_form.html", {"mode": "create", "obj": AssetModelName()})


@admin_required
def model_name_edit(request, pk):
    obj = get_object_or_404(AssetModelName, pk=pk)
    if request.method == "POST":
        error = _save_model_name(request, obj=obj)
        if error is None:
            messages.success(request, f"Model name '{obj.name}' updated.")
            return redirect("assets:dropdowns_home")
        return render(request, "assets/catalog/model_name_form.html",
                      {"mode": "edit", "obj": obj, "post": request.POST, "form_error": error})
    return render(request, "assets/catalog/model_name_form.html", {"mode": "edit", "obj": obj})


@admin_required
@require_POST
def model_name_toggle(request, pk):
    obj = get_object_or_404(AssetModelName, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active", "updated_at"])
    messages.success(request, f"Model name '{obj.name}' {'activated' if obj.is_active else 'deactivated'}.")
    return redirect("assets:dropdowns_home")


@admin_required
@require_POST
def model_name_delete(request, pk):
    obj = get_object_or_404(AssetModelName, pk=pk)
    if AssetItem.objects.filter(model_name=obj.name, is_deleted=False).exists():
        messages.error(request, f"Cannot delete '{obj.name}' — assets reference it. Deactivate instead.")
        return redirect("assets:dropdowns_home")
    name = obj.name
    obj.delete()
    messages.success(request, f"Model name '{name}' deleted.")
    return redirect("assets:dropdowns_home")


# ── Vendor CRUD ──────────────────────────────────────────────────────────────

@admin_required
def vendor_create(request):
    if request.method == "POST":
        error = _save_vendor(request, obj=None)
        if error is None:
            messages.success(request, "Vendor added.")
            return redirect("assets:dropdowns_home")
        return render(request, "assets/catalog/vendor_form.html",
                      {"mode": "create", "obj": Vendor(), "post": request.POST, "form_error": error})
    return render(request, "assets/catalog/vendor_form.html", {"mode": "create", "obj": Vendor()})


@admin_required
def vendor_edit(request, pk):
    obj = get_object_or_404(Vendor, pk=pk)
    if request.method == "POST":
        error = _save_vendor(request, obj=obj)
        if error is None:
            messages.success(request, f"Vendor '{obj.name}' updated.")
            return redirect("assets:dropdowns_home")
        return render(request, "assets/catalog/vendor_form.html",
                      {"mode": "edit", "obj": obj, "post": request.POST, "form_error": error})
    return render(request, "assets/catalog/vendor_form.html", {"mode": "edit", "obj": obj})


@admin_required
@require_POST
def vendor_toggle(request, pk):
    obj = get_object_or_404(Vendor, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active", "updated_at"])
    messages.success(request, f"Vendor '{obj.name}' {'activated' if obj.is_active else 'deactivated'}.")
    return redirect("assets:dropdowns_home")


@admin_required
@require_POST
def vendor_delete(request, pk):
    obj = get_object_or_404(Vendor, pk=pk)
    if AssetItem.objects.filter(supplier=obj.name, is_deleted=False).exists():
        messages.error(request, f"Cannot delete '{obj.name}' — assets reference it. Deactivate instead.")
        return redirect("assets:dropdowns_home")
    name = obj.name
    obj.delete()
    messages.success(request, f"Vendor '{name}' deleted.")
    return redirect("assets:dropdowns_home")


# ── Spec Choices ─────────────────────────────────────────────────────────────

# Friendly display names for each spec key
SPEC_KEY_LABELS = {
    "cpu_model":       "CPU Model (i3 / i5 / i7 / i9 …)",
    "ram_type":        "RAM Type (DDR4 / DDR5 …)",
    "storage_type":    "Storage Type (SSD / HDD …)",
    "os_name":         "Operating System Name",
    "gpu_chipset":     "GPU Chipset",
    "gpu_memory_type": "GPU Memory Type",
    "gpu_capacity":    "GPU Capacity",
}

ALL_SPEC_KEYS = list(SPEC_KEY_LABELS.keys())


@admin_required
def spec_choices_home(request):
    choices = SpecChoice.objects.order_by("spec_key", "order", "label")
    grouped = {}
    for sc in choices:
        grouped.setdefault(sc.spec_key, []).append(sc)
    # Include all known keys even if empty
    for key in ALL_SPEC_KEYS:
        grouped.setdefault(key, [])
    groups = [
        {"key": k, "label": SPEC_KEY_LABELS.get(k, k), "choices": grouped[k]}
        for k in ALL_SPEC_KEYS
    ]
    # Also show any extra keys added manually that aren't in the standard list
    extra_keys = [k for k in grouped if k not in ALL_SPEC_KEYS]
    for k in sorted(extra_keys):
        groups.append({"key": k, "label": k, "choices": grouped[k]})
    return render(request, "assets/catalog/spec_choices_home.html", {
        "groups": groups,
        "all_spec_keys": ALL_SPEC_KEYS,
        "spec_key_labels": SPEC_KEY_LABELS,
    })


@admin_required
def spec_choice_create(request):
    pre_key = request.GET.get("spec_key", "")
    if request.method == "POST":
        error = _save_spec_choice(request, obj=None)
        if error is None:
            messages.success(request, "Choice added.")
            return redirect("assets:spec_choices_home")
        return render(request, "assets/catalog/spec_choice_form.html", {
            "mode": "create", "obj": SpecChoice(), "post": request.POST, "form_error": error,
            "all_spec_keys": ALL_SPEC_KEYS, "spec_key_labels": SPEC_KEY_LABELS,
        })
    return render(request, "assets/catalog/spec_choice_form.html", {
        "mode": "create", "obj": SpecChoice(), "pre_key": pre_key,
        "all_spec_keys": ALL_SPEC_KEYS, "spec_key_labels": SPEC_KEY_LABELS,
    })


@admin_required
def spec_choice_edit(request, pk):
    obj = get_object_or_404(SpecChoice, pk=pk)
    if request.method == "POST":
        error = _save_spec_choice(request, obj=obj)
        if error is None:
            messages.success(request, "Choice updated.")
            return redirect("assets:spec_choices_home")
        return render(request, "assets/catalog/spec_choice_form.html", {
            "mode": "edit", "obj": obj, "post": request.POST, "form_error": error,
            "all_spec_keys": ALL_SPEC_KEYS, "spec_key_labels": SPEC_KEY_LABELS,
        })
    return render(request, "assets/catalog/spec_choice_form.html", {
        "mode": "edit", "obj": obj,
        "all_spec_keys": ALL_SPEC_KEYS, "spec_key_labels": SPEC_KEY_LABELS,
    })


@admin_required
@require_POST
def spec_choice_toggle(request, pk):
    obj = get_object_or_404(SpecChoice, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active"])
    messages.success(request, f"Choice '{obj.display_label()}' {'activated' if obj.is_active else 'deactivated'}.")
    return redirect("assets:spec_choices_home")


@admin_required
@require_POST
def spec_choice_delete(request, pk):
    obj = get_object_or_404(SpecChoice, pk=pk)
    label = obj.display_label()
    obj.delete()
    messages.success(request, f"Choice '{label}' deleted.")
    return redirect("assets:spec_choices_home")


# ── Dropdown helpers ─────────────────────────────────────────────────────────

def _save_brand(request, obj) -> str | None:
    name = request.POST.get("name", "").strip()
    if not name:
        return "Brand name is required."
    clash = Brand.objects.filter(name__iexact=name)
    if obj:
        clash = clash.exclude(pk=obj.pk)
    if clash.exists():
        return f"A brand named '{name}' already exists."
    if obj is None:
        obj = Brand()
    obj.name = name
    obj.is_active = request.POST.get("is_active") == "on"
    obj.save()
    return None


def _save_model_name(request, obj) -> str | None:
    name = request.POST.get("name", "").strip()
    if not name:
        return "Model name is required."
    clash = AssetModelName.objects.filter(name__iexact=name)
    if obj:
        clash = clash.exclude(pk=obj.pk)
    if clash.exists():
        return f"A model named '{name}' already exists."
    if obj is None:
        obj = AssetModelName()
    obj.name = name
    obj.is_active = request.POST.get("is_active") == "on"
    obj.save()
    return None


def _save_vendor(request, obj) -> str | None:
    name = request.POST.get("name", "").strip()
    if not name:
        return "Vendor name is required."
    clash = Vendor.objects.filter(name__iexact=name)
    if obj:
        clash = clash.exclude(pk=obj.pk)
    if clash.exists():
        return f"A vendor named '{name}' already exists."
    if obj is None:
        obj = Vendor()
    obj.name = name
    obj.contact_info = request.POST.get("contact_info", "").strip()
    obj.is_active = request.POST.get("is_active") == "on"
    obj.save()
    return None


def _save_spec_choice(request, obj) -> str | None:
    spec_key = request.POST.get("spec_key", "").strip()
    value = request.POST.get("value", "").strip()
    label = request.POST.get("label", "").strip()
    try:
        order = int(request.POST.get("order", "0"))
    except (ValueError, TypeError):
        order = 0
    if not spec_key:
        return "Spec key is required."
    if not value:
        return "Value is required."
    clash = SpecChoice.objects.filter(spec_key=spec_key, value__iexact=value)
    if obj:
        clash = clash.exclude(pk=obj.pk)
    if clash.exists():
        return f"A choice with value '{value}' already exists for '{spec_key}'."
    if obj is None:
        obj = SpecChoice()
    obj.spec_key = spec_key
    obj.value = value
    obj.label = label
    obj.order = order
    obj.is_active = request.POST.get("is_active") == "on"
    obj.save()
    return None
