"""
Catalogue app views.

Two concerns live here:

* **Dependent dropdown JSON API** (``/catalogue/sub-assets|brands|models|spec/``) —
  consumed by the Add/Edit Asset cascade. Read-only, honours ``is_active=True``.
* **Master Data management page** (``/catalogue/manage/``) — the single Admin page
  that replaces the old Asset Catalog / Dropdowns / Spec Options pages. It drills
  Main → Sub → Brand → Model and edits the per-Sub spec-field schema.
"""

import re
from collections import Counter

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from config.permissions import admin_required, viewer_required

from assets.models import AssetCategory, AssetItem, AssetType, Vendor

from .models import CatalogBrand, CatalogModel, SubAssetSpecField
from .specs import field_dicts, slugify_key


# ── Dependent dropdown JSON API ───────────────────────────────────────────────

@viewer_required
def api_sub_assets(request):
    """Active Sub Assets (AssetType) for a Main Asset (category)."""
    main = request.GET.get("main")
    rows = []
    if main:
        rows = [
            {"id": t.pk, "name": t.name}
            for t in AssetType.objects.filter(category_id=main, is_active=True).order_by("name")
        ]
    return JsonResponse({"results": rows})


@viewer_required
def api_brands(request):
    """Active Brands for a Sub Asset."""
    sub = request.GET.get("sub")
    rows = []
    if sub:
        rows = [
            {"id": b.pk, "name": b.name}
            for b in CatalogBrand.objects.filter(sub_asset_id=sub, is_active=True).order_by("name")
        ]
    return JsonResponse({"results": rows})


@viewer_required
def api_models(request):
    """Active Models for a Brand."""
    brand = request.GET.get("brand")
    rows = []
    if brand:
        rows = [
            {"id": m.pk, "name": m.name}
            for m in CatalogModel.objects.filter(brand_id=brand, is_active=True).order_by("name")
        ]
    return JsonResponse({"results": rows})


@viewer_required
def api_spec(request):
    """
    Specification schema for the chosen Model's Sub Asset.

    Returns the master-data field definitions so the form can render widgets.
    ``specification_template`` is a plain-text rendering kept for compatibility
    with the documented API contract.
    """
    model_id = request.GET.get("model")
    fields, sub_id = [], None
    if model_id:
        model = (
            CatalogModel.objects.filter(pk=model_id)
            .select_related("brand__sub_asset")
            .first()
        )
        if model:
            sub_id = model.brand.sub_asset_id
            fields = field_dicts(model.brand.sub_asset)
    template = "\n".join(
        f"{f['label']}: {', '.join(f['options']) if f['options'] else (f['unit'] or '')}".rstrip(": ").rstrip()
        for f in fields
    )
    return JsonResponse({
        "sub_asset": sub_id,
        "fields": fields,
        "specification_template": template,
    })


# ── Master Data management page ───────────────────────────────────────────────

def _manage_url(main=None, sub=None, brand=None) -> str:
    params = {}
    if main:
        params["main"] = main
    if sub:
        params["sub"] = sub
    if brand:
        params["brand"] = brand
    base = reverse("catalogue:manage")
    return f"{base}?{urlencode(params)}" if params else base


def _selected(request):
    """Resolve the currently selected main/sub/brand ids from the request."""
    def _int(name):
        val = request.POST.get(name) or request.GET.get(name)
        try:
            return int(val)
        except (TypeError, ValueError):
            return None
    return _int("main"), _int("sub"), _int("brand")


# ── Asset-usage guard ─────────────────────────────────────────────────────────
# A master-data node may be deleted only when no live (non-deleted) asset uses it.
# Sub Asset is a real FK (asset_type); Brand/Model are matched by free-text name,
# the same convention the asset form stores them under.

def _assets_using(*, main=None, sub=None, brand=None, model=None):
    qs = AssetItem.objects.filter(is_deleted=False)
    if main is not None:
        return qs.filter(asset_type__category=main)
    if sub is not None:
        return qs.filter(asset_type=sub)
    if brand is not None:
        return qs.filter(asset_type=brand.sub_asset, brand__iexact=brand.name)
    if model is not None:
        return qs.filter(
            asset_type=model.brand.sub_asset,
            brand__iexact=model.brand.name,
            model_name__iexact=model.name,
        )
    return qs.none()


@admin_required
def manage(request):
    main_id, sub_id, brand_id = _selected(request)

    # Live-asset usage drives the "in use" badge and whether Delete is allowed.
    # Main/Sub are FK-counted; Brand/Model are matched by free-text name.
    mains = list(
        AssetCategory.objects.annotate(
            sub_count=Count("asset_types", distinct=True),
            asset_count=Count("asset_types__items", filter=Q(asset_types__items__is_deleted=False), distinct=True),
        ).order_by("name")
    )
    main = next((m for m in mains if m.pk == main_id), None)

    subs, sub = [], None
    if main:
        subs = list(
            AssetType.objects.filter(category=main)
            .annotate(
                brand_count=Count("catalog_brands", distinct=True),
                asset_count=Count("items", filter=Q(items__is_deleted=False), distinct=True),
            )
            .order_by("name")
        )
        sub = next((s for s in subs if s.pk == sub_id), None)

    brands, brand = [], None
    spec_fields = []
    if sub:
        brands = list(
            CatalogBrand.objects.filter(sub_asset=sub)
            .annotate(model_count=Count("catalog_models", distinct=True))
            .order_by("name")
        )
        # Name-based usage: count live assets of this Sub grouped by brand name.
        brand_usage = Counter(
            (n or "").strip().lower()
            for n in AssetItem.objects.filter(asset_type=sub, is_deleted=False).values_list("brand", flat=True)
        )
        for b in brands:
            b.asset_count = brand_usage.get(b.name.strip().lower(), 0)
        brand = next((b for b in brands if b.pk == brand_id), None)
        spec_fields = list(sub.spec_fields.order_by("order", "id"))

    models = []
    if brand:
        models = list(CatalogModel.objects.filter(brand=brand).order_by("name"))
        # Name-based usage: live assets of this Sub with this brand, grouped by model name.
        model_usage = Counter(
            (n or "").strip().lower()
            for n in AssetItem.objects.filter(
                asset_type=sub, brand__iexact=brand.name, is_deleted=False
            ).values_list("model_name", flat=True)
        )
        for mo in models:
            mo.asset_count = model_usage.get(mo.name.strip().lower(), 0)

    return render(request, "catalogue/manage.html", {
        "mains": mains,
        "subs": subs,
        "brands": brands,
        "models": models,
        "spec_fields": spec_fields,
        "sel_main": main,
        "sel_sub": sub,
        "sel_brand": brand,
        "vendors": Vendor.objects.order_by("name"),
        "widget_choices": SubAssetSpecField.Widget.choices,
    })


# ── Main Asset (AssetCategory) ────────────────────────────────────────────────

@admin_required
@require_POST
def main_save(request):
    pk = request.POST.get("pk")
    name = request.POST.get("name", "").strip()
    if not name:
        messages.error(request, "Main Asset name is required.")
        return redirect(_manage_url(main=pk or None))
    clash = AssetCategory.objects.filter(name__iexact=name).exclude(pk=pk or 0)
    if clash.exists():
        messages.error(request, f"A Main Asset named '{name}' already exists.")
        return redirect(_manage_url(main=pk or None))
    obj = get_object_or_404(AssetCategory, pk=pk) if pk else AssetCategory()
    obj.name = name
    obj.save()
    messages.success(request, "Main Asset saved.")
    return redirect(_manage_url(main=obj.pk))


@admin_required
@require_POST
def main_toggle(request, pk):
    obj = get_object_or_404(AssetCategory, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active", "updated_at"])
    return redirect(_manage_url(main=obj.pk))


@admin_required
@require_POST
def main_delete(request, pk):
    obj = get_object_or_404(AssetCategory, pk=pk)
    used = _assets_using(main=obj).count()
    if used:
        messages.error(request, f"Cannot delete '{obj.name}' — {used} asset(s) still use it. Reassign or remove them first.")
        return redirect(_manage_url(main=obj.pk))
    name = obj.name
    with transaction.atomic():
        subs = AssetType.objects.filter(category=obj)
        CatalogModel.objects.filter(brand__sub_asset__in=subs).delete()
        CatalogBrand.objects.filter(sub_asset__in=subs).delete()
        subs.delete()  # cascades each Sub's spec fields
        obj.delete()
    messages.success(request, f"Deleted '{name}' and its sub-assets, brands and models.")
    return redirect(_manage_url())


# ── Sub Asset (AssetType) ─────────────────────────────────────────────────────

@admin_required
@require_POST
def sub_save(request):
    main_id, _, _ = _selected(request)
    pk = request.POST.get("pk")
    name = request.POST.get("name", "").strip()
    obj = get_object_or_404(AssetType, pk=pk) if pk else None
    category_id = obj.category_id if obj else main_id
    if not category_id:
        messages.error(request, "Select a Main Asset first.")
        return redirect(_manage_url(main=main_id))
    if not name:
        messages.error(request, "Sub Asset name is required.")
        return redirect(_manage_url(main=category_id, sub=pk or None))
    clash = AssetType.objects.filter(category_id=category_id, name__iexact=name).exclude(pk=pk or 0)
    if clash.exists():
        messages.error(request, f"A Sub Asset named '{name}' already exists here.")
        return redirect(_manage_url(main=category_id, sub=pk or None))
    if obj is None:
        obj = AssetType(category_id=category_id)
    obj.name = name
    obj.has_components = request.POST.get("has_components") == "on"
    obj.save()
    messages.success(request, "Sub Asset saved.")
    return redirect(_manage_url(main=category_id, sub=obj.pk))


@admin_required
@require_POST
def sub_toggle(request, pk):
    obj = get_object_or_404(AssetType, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active", "updated_at"])
    return redirect(_manage_url(main=obj.category_id, sub=obj.pk))


@admin_required
@require_POST
def sub_delete(request, pk):
    obj = get_object_or_404(AssetType, pk=pk)
    main_id = obj.category_id
    used = _assets_using(sub=obj).count()
    if used:
        messages.error(request, f"Cannot delete '{obj.name}' — {used} asset(s) of this type exist. Reassign or remove them first.")
        return redirect(_manage_url(main=main_id, sub=obj.pk))
    name = obj.name
    with transaction.atomic():
        CatalogModel.objects.filter(brand__sub_asset=obj).delete()
        CatalogBrand.objects.filter(sub_asset=obj).delete()
        obj.delete()  # cascades spec fields
    messages.success(request, f"Deleted '{name}' and its brands, models and spec fields.")
    return redirect(_manage_url(main=main_id))


# ── Brand (CatalogBrand) ──────────────────────────────────────────────────────

@admin_required
@require_POST
def brand_save(request):
    main_id, sub_id, _ = _selected(request)
    pk = request.POST.get("pk")
    name = request.POST.get("name", "").strip()
    obj = get_object_or_404(CatalogBrand, pk=pk) if pk else None
    target_sub = obj.sub_asset_id if obj else sub_id
    if not target_sub:
        messages.error(request, "Select a Sub Asset first.")
        return redirect(_manage_url(main=main_id, sub=sub_id))
    if not name:
        messages.error(request, "Brand name is required.")
        return redirect(_manage_url(main=main_id, sub=target_sub, brand=pk or None))
    clash = CatalogBrand.objects.filter(sub_asset_id=target_sub, name__iexact=name).exclude(pk=pk or 0)
    if clash.exists():
        messages.error(request, f"A Brand named '{name}' already exists here.")
        return redirect(_manage_url(main=main_id, sub=target_sub, brand=pk or None))
    if obj is None:
        obj = CatalogBrand(sub_asset_id=target_sub)
    obj.name = name
    obj.save()
    messages.success(request, "Brand saved.")
    return redirect(_manage_url(main=main_id, sub=target_sub, brand=obj.pk))


@admin_required
@require_POST
def brand_toggle(request, pk):
    obj = get_object_or_404(CatalogBrand, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active", "updated_at"])
    return redirect(_manage_url(main=obj.sub_asset.category_id, sub=obj.sub_asset_id, brand=obj.pk))


@admin_required
@require_POST
def brand_delete(request, pk):
    obj = get_object_or_404(CatalogBrand.objects.select_related("sub_asset"), pk=pk)
    main_id, sub_id = obj.sub_asset.category_id, obj.sub_asset_id
    used = _assets_using(brand=obj).count()
    if used:
        messages.error(request, f"Cannot delete '{obj.name}' — {used} asset(s) use this brand. Reassign or remove them first.")
        return redirect(_manage_url(main=main_id, sub=sub_id, brand=obj.pk))
    name = obj.name
    with transaction.atomic():
        CatalogModel.objects.filter(brand=obj).delete()
        obj.delete()
    messages.success(request, f"Deleted '{name}' and its models.")
    return redirect(_manage_url(main=main_id, sub=sub_id))


# ── Model (CatalogModel) ──────────────────────────────────────────────────────

@admin_required
@require_POST
def model_save(request):
    main_id, sub_id, brand_id = _selected(request)
    pk = request.POST.get("pk")
    name = request.POST.get("name", "").strip()
    obj = get_object_or_404(CatalogModel, pk=pk) if pk else None
    target_brand = obj.brand_id if obj else brand_id
    if not target_brand:
        messages.error(request, "Select a Brand first.")
        return redirect(_manage_url(main=main_id, sub=sub_id, brand=brand_id))
    if not name:
        messages.error(request, "Model name is required.")
        return redirect(_manage_url(main=main_id, sub=sub_id, brand=target_brand))
    clash = CatalogModel.objects.filter(brand_id=target_brand, name__iexact=name).exclude(pk=pk or 0)
    if clash.exists():
        messages.error(request, f"A Model named '{name}' already exists here.")
        return redirect(_manage_url(main=main_id, sub=sub_id, brand=target_brand))
    if obj is None:
        obj = CatalogModel(brand_id=target_brand)
    obj.name = name
    obj.save()
    messages.success(request, "Model saved.")
    return redirect(_manage_url(main=main_id, sub=sub_id, brand=target_brand))


@admin_required
@require_POST
def model_toggle(request, pk):
    obj = get_object_or_404(CatalogModel.objects.select_related("brand__sub_asset"), pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active", "updated_at"])
    b = obj.brand
    return redirect(_manage_url(main=b.sub_asset.category_id, sub=b.sub_asset_id, brand=b.pk))


@admin_required
@require_POST
def model_delete(request, pk):
    obj = get_object_or_404(CatalogModel.objects.select_related("brand__sub_asset"), pk=pk)
    b = obj.brand
    main_id, sub_id, brand_id = b.sub_asset.category_id, b.sub_asset_id, b.pk
    used = _assets_using(model=obj).count()
    if used:
        messages.error(request, f"Cannot delete '{obj.name}' — {used} asset(s) use this model. Reassign or remove them first.")
        return redirect(_manage_url(main=main_id, sub=sub_id, brand=brand_id))
    obj.delete()
    messages.success(request, "Model deleted.")
    return redirect(_manage_url(main=main_id, sub=sub_id, brand=brand_id))


# ── Spec fields (SubAssetSpecField) ───────────────────────────────────────────

def _parse_options(raw: str) -> list[str]:
    """Split a comma/newline separated options string into a clean list."""
    parts = re.split(r"[,\n]", raw or "")
    seen, out = set(), []
    for p in (x.strip() for x in parts):
        if p and p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return out


@admin_required
@require_POST
def specfield_save(request):
    main_id, sub_id, brand_id = _selected(request)
    pk = request.POST.get("pk")
    label = request.POST.get("label", "").strip()
    widget = request.POST.get("widget", "text").strip()
    obj = get_object_or_404(SubAssetSpecField, pk=pk) if pk else None
    target_sub = obj.sub_asset_id if obj else sub_id
    back = _manage_url(main=main_id, sub=target_sub, brand=brand_id)
    if not target_sub:
        messages.error(request, "Select a Sub Asset first.")
        return redirect(back)
    if not label:
        messages.error(request, "Field label is required.")
        return redirect(back)
    if widget not in SubAssetSpecField.Widget.values:
        widget = SubAssetSpecField.Widget.TEXT
    key = obj.key if obj else slugify_key(label)
    if not key:
        messages.error(request, "Could not derive a key from that label.")
        return redirect(back)
    clash = SubAssetSpecField.objects.filter(sub_asset_id=target_sub, key=key).exclude(pk=pk or 0)
    if clash.exists():
        messages.error(request, f"A field with key '{key}' already exists here.")
        return redirect(back)
    if obj is None:
        last = SubAssetSpecField.objects.filter(sub_asset_id=target_sub).count()
        obj = SubAssetSpecField(sub_asset_id=target_sub, key=key, order=last)
    obj.label = label
    obj.widget = widget
    obj.unit = request.POST.get("unit", "").strip()
    obj.options = _parse_options(request.POST.get("options", ""))
    obj.required = request.POST.get("required") == "on"
    obj.save()
    messages.success(request, "Spec field saved.")
    return redirect(back)


@admin_required
@require_POST
def specfield_toggle(request, pk):
    obj = get_object_or_404(SubAssetSpecField, pk=pk)
    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active", "updated_at"])
    return redirect(_manage_url(main=obj.sub_asset.category_id, sub=obj.sub_asset_id))


@admin_required
@require_POST
def specfield_delete(request, pk):
    obj = get_object_or_404(SubAssetSpecField, pk=pk)
    main_id, sub_id = obj.sub_asset.category_id, obj.sub_asset_id
    obj.delete()
    messages.success(request, "Spec field deleted.")
    return redirect(_manage_url(main=main_id, sub=sub_id))


@admin_required
@require_POST
def specfield_move(request, pk):  # noqa: C901
    """Reorder a spec field up or down within its Sub Asset."""
    obj = get_object_or_404(SubAssetSpecField, pk=pk)
    direction = request.POST.get("dir")
    siblings = list(obj.sub_asset.spec_fields.order_by("order", "id"))
    idx = next((i for i, s in enumerate(siblings) if s.pk == obj.pk), None)
    if idx is not None:
        swap = idx - 1 if direction == "up" else idx + 1
        if 0 <= swap < len(siblings):
            siblings[idx], siblings[swap] = siblings[swap], siblings[idx]
            for i, s in enumerate(siblings):
                if s.order != i:
                    SubAssetSpecField.objects.filter(pk=s.pk).update(order=i)
    return redirect(_manage_url(main=obj.sub_asset.category_id, sub=obj.sub_asset_id))
