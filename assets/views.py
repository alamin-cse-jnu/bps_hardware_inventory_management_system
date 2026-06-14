import io
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
import json

from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from assignments.models import Assignment, AlertStatus, InactiveHolderAlert
from config.permissions import it_officer_required, viewer_required
from locations.models import Location

from .models import (
    AssetCategory, AssetItem, AssetModelName, AssetType,
    Brand, SpecChoice, Vendor, WorkOrder,
)
from .services.excel_import import (
    SESSION_KEY_COLS,
    SESSION_KEY_ROWS,
    SESSION_KEY_TYPE,
    ExcelImportExecutor,
    ExcelImportValidator,
    ExcelTemplateGenerator,
    _get_type_prefix,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date_safe(val):
    if not val or not str(val).strip():
        return None
    try:
        return datetime.strptime(str(val).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_decimal_safe(val):
    if not val or not str(val).strip():
        return None
    try:
        return Decimal(str(val).strip())
    except (InvalidOperation, ValueError):
        return None


def _generate_asset_tag(asset_type):
    year = timezone.now().year
    prefix = _get_type_prefix(asset_type.name)
    key = f"{prefix}-{year}"
    existing = AssetItem.objects.filter(
        asset_tag__startswith=f"{key}-"
    ).values_list("asset_tag", flat=True)
    max_seq = 0
    for tag in existing:
        suffix = tag[len(key) + 1:]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    return f"{key}-{max_seq + 1:04d}"


def _validate_asset_form(data, spec_schema, exclude_pk=None):
    errors = {}
    if not data.get("asset_type"):
        errors["asset_type"] = "Asset type is required."
    if not data.get("brand", "").strip():
        errors["brand"] = "Brand is required."
    if not data.get("model_name", "").strip():
        errors["model_name"] = "Model name is required."
    tag = data.get("asset_tag", "").strip()
    if tag:
        qs = AssetItem.objects.filter(asset_tag=tag)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            errors["asset_tag"] = f"Asset tag '{tag}' is already in use."
    for field in ("purchase_date", "warranty_expiry", "amc_expiry"):
        val = data.get(field, "").strip()
        if val:
            try:
                datetime.strptime(val, "%Y-%m-%d")
            except ValueError:
                errors[field] = "Use format YYYY-MM-DD."
    cost = data.get("purchase_cost", "").strip()
    if cost:
        try:
            Decimal(cost)
        except (InvalidOperation, ValueError):
            errors["purchase_cost"] = "Enter a valid number (e.g. 45000.00)."
    return errors


def _locations_qs():
    return Location.objects.filter(is_active=True).select_related("parent__parent")


def _types_qs():
    return AssetType.objects.filter(is_active=True).select_related("category").order_by("category__name", "name")


def _catalog_context():
    """Extra context for asset create/edit forms: dropdown lists."""
    choices = {}
    for sc in SpecChoice.objects.filter(is_active=True).order_by("spec_key", "order", "label"):
        choices.setdefault(sc.spec_key, []).append((sc.value, sc.display_label()))
    return {
        "brands": Brand.objects.filter(is_active=True),
        "model_names": AssetModelName.objects.filter(is_active=True),
        "vendors": Vendor.objects.filter(is_active=True),
        "spec_choices_by_key": choices,
    }


def _save_work_order(request):
    """Create and return a WorkOrder from the uploaded file, or None."""
    f = request.FILES.get("work_order_file")
    if not f:
        return None
    return WorkOrder.objects.create(
        reference=request.POST.get("work_order_reference", "").strip(),
        document=f,
        description=request.POST.get("work_order_description", "").strip(),
        uploaded_by=request.user,
    )


# Keys whose spec values are stored as dicts (composite fields)
_COMPOSITE_SPEC_KEYS = {"ram", "storage", "display", "display_monitor", "os", "cpu", "gpu"}


def _collect_specs(spec_schema, post_data):
    """Build the specifications dict from POST data, handling composite keys."""
    specs = {}
    for key in spec_schema:
        if key == "ram":
            specs[key] = {
                "qty": post_data.get("spec_ram_qty", "").strip(),
                "type": post_data.get("spec_ram_type", "").strip(),
            }
        elif key == "storage":
            specs[key] = {
                "qty": post_data.get("spec_storage_qty", "").strip(),
                "unit": post_data.get("spec_storage_unit", "GB").strip(),
                "type": post_data.get("spec_storage_type", "").strip(),
            }
        elif key in ("display", "display_monitor"):
            specs[key] = {
                "size": post_data.get(f"spec_{key}_size", "").strip(),
            }
        elif key == "os":
            specs[key] = {
                "name": post_data.get("spec_os_name", "").strip(),
                "licensed": post_data.get("spec_os_licensed", "").strip(),
            }
        elif key == "cpu":
            specs[key] = {
                "brand": post_data.get("spec_cpu_brand", "").strip(),
                "model": post_data.get("spec_cpu_model", "").strip(),
                "cores": post_data.get("spec_cpu_cores", "").strip(),
                "generation": post_data.get("spec_cpu_generation", "").strip(),
            }
        elif key == "gpu":
            specs[key] = {
                "chipset": post_data.get("spec_gpu_chipset", "").strip(),
                "memory_type": post_data.get("spec_gpu_memory_type", "").strip(),
                "capacity": post_data.get("spec_gpu_capacity", "").strip(),
            }
        else:
            specs[key] = post_data.get(f"spec_{key}", "").strip()
    return specs


def _spec_display_value(key, post_data):
    """Reconstruct a spec display value (dict or string) from raw POST data."""
    if key == "ram":
        return {"qty": post_data.get("spec_ram_qty", ""), "type": post_data.get("spec_ram_type", "")}
    elif key == "storage":
        return {"qty": post_data.get("spec_storage_qty", ""), "unit": post_data.get("spec_storage_unit", "GB"), "type": post_data.get("spec_storage_type", "")}
    elif key in ("display", "display_monitor"):
        return {"size": post_data.get(f"spec_{key}_size", "")}
    elif key == "os":
        return {"name": post_data.get("spec_os_name", ""), "licensed": post_data.get("spec_os_licensed", "")}
    elif key == "cpu":
        return {
            "brand": post_data.get("spec_cpu_brand", ""),
            "model": post_data.get("spec_cpu_model", ""),
            "cores": post_data.get("spec_cpu_cores", ""),
            "generation": post_data.get("spec_cpu_generation", ""),
        }
    elif key == "gpu":
        return {
            "chipset": post_data.get("spec_gpu_chipset", ""),
            "memory_type": post_data.get("spec_gpu_memory_type", ""),
            "capacity": post_data.get("spec_gpu_capacity", ""),
        }
    return post_data.get(f"spec_{key}", "")


# ---------------------------------------------------------------------------
# Asset register print
# ---------------------------------------------------------------------------

@viewer_required
def asset_register_print(request):
    from assignments.models import Assignment
    status_filter = request.GET.get("status", "").strip()
    qs = (
        AssetItem.objects.filter(is_deleted=False)
        .select_related("asset_type__category", "storage_location")
        .order_by("asset_tag")
    )
    if status_filter:
        qs = qs.filter(status=status_filter)
    assets = list(qs)
    active_map = {
        a.asset_id: a
        for a in Assignment.objects.filter(
            asset_id__in=[a.pk for a in assets],
            returned_at__isnull=True,
        ).select_related(
            "assignee__employee", "assignee__mp",
            "assignee__office", "assignee__location",
        )
    }
    rows = [(asset, active_map.get(asset.pk)) for asset in assets]
    status_label = dict(AssetItem.Status.choices).get(status_filter, "All")
    return render(request, "assets/register_print.html", {
        "rows": rows,
        "status_filter": status_filter,
        "status_label": status_label,
        "total": len(assets),
        "generated_at": timezone.now(),
    })


# Global search
# ---------------------------------------------------------------------------

@viewer_required
def global_search(request):
    from assignments.models import Assignment
    q = request.GET.get("q", "").strip()
    results = []
    if len(q) >= 2:
        assets = list(
            AssetItem.objects.filter(is_deleted=False)
            .filter(
                Q(asset_tag__icontains=q) |
                Q(serial_number__icontains=q) |
                Q(brand__icontains=q) |
                Q(model_name__icontains=q)
            )
            .select_related("asset_type__category")[:10]
        )
        active_map = {
            a.asset_id: a
            for a in Assignment.objects.filter(
                asset_id__in=[a.pk for a in assets],
                returned_at__isnull=True,
            ).select_related(
                "assignee__employee", "assignee__mp",
                "assignee__office", "assignee__location",
            )
        }
        results = [(asset, active_map.get(asset.pk)) for asset in assets]

    return render(request, "assets/partials/global_search_results.html", {
        "results": results,
        "q": q,
    })


# Dashboard
# ---------------------------------------------------------------------------

@viewer_required
def dashboard(request):
    from lifecycle.models import LifecycleEvent
    from sync_prp.models import SyncLog

    qs = AssetItem.objects.filter(is_deleted=False)
    total = qs.count()
    assigned_count = qs.filter(status=AssetItem.Status.ASSIGNED).count()
    in_stock_count = qs.filter(status=AssetItem.Status.IN_STOCK).count()
    maintenance_count = qs.filter(status=AssetItem.Status.MAINTENANCE).count()
    lost_count = qs.filter(status=AssetItem.Status.LOST).count()
    damaged_count = qs.filter(status=AssetItem.Status.DAMAGED).count()
    disposed_count = qs.filter(status=AssetItem.Status.DISPOSED).count()
    issues_count = maintenance_count + lost_count + damaged_count

    horizon = timezone.now().date() + timedelta(days=30)
    today = timezone.now().date()
    expiring_assets = qs.filter(
        Q(warranty_expiry__gt=today, warranty_expiry__lte=horizon) |
        Q(amc_expiry__gt=today, amc_expiry__lte=horizon)
    ).select_related("asset_type").order_by("warranty_expiry", "amc_expiry")[:10]

    open_alerts = InactiveHolderAlert.objects.filter(
        status=AlertStatus.OPEN
    ).select_related(
        "assignee__employee", "assignee__mp", "assignee__office",
    ).order_by("-raised_at")[:10]

    recent_assignments = Assignment.objects.select_related(
        "asset__asset_type", "assignee__employee", "assignee__mp",
        "assignee__office", "performed_by",
    ).order_by("-assigned_at")[:8]

    recent_events = LifecycleEvent.objects.select_related(
        "asset", "performed_by",
    ).order_by("-occurred_at")[:5]

    last_sync = SyncLog.objects.order_by("-started_at").first()

    # Chart data
    status_chart = json.dumps({
        "labels": ["In Stock", "Assigned", "Maintenance", "Lost", "Damaged", "Disposed"],
        "data": [in_stock_count, assigned_count, maintenance_count, lost_count, damaged_count, disposed_count],
        "colors": ["#10B981", "#3B82F6", "#F59E0B", "#EF4444", "#F97316", "#9CA3AF"],
    })

    # Category + asset-type breakdown
    type_qs = (
        AssetType.objects.filter(is_active=True)
        .annotate(count=Count("items", filter=Q(items__is_deleted=False)))
        .filter(count__gt=0)
        .select_related("category")
        .order_by("category__name", "-count")
    )
    _cat_map = {}
    for t in type_qs:
        cat = t.category
        if cat.pk not in _cat_map:
            _cat_map[cat.pk] = {"name": cat.name, "types": [], "total": 0}
        _cat_map[cat.pk]["types"].append({"name": t.name, "count": t.count})
        _cat_map[cat.pk]["total"] += t.count
    category_breakdown = sorted(_cat_map.values(), key=lambda x: -x["total"])
    breakdown_max = category_breakdown[0]["total"] if category_breakdown else 1

    return render(request, "dashboard.html", {
        "total": total,
        "assigned_count": assigned_count,
        "in_stock_count": in_stock_count,
        "issues_count": issues_count,
        "disposed_count": disposed_count,
        "expiring_assets": expiring_assets,
        "open_alerts": open_alerts,
        "recent_assignments": recent_assignments,
        "recent_events": recent_events,
        "last_sync": last_sync,
        "status_chart": status_chart,
        "category_breakdown": category_breakdown,
        "breakdown_max": breakdown_max,
    })


# ---------------------------------------------------------------------------
# Asset list / detail
# ---------------------------------------------------------------------------

@viewer_required
def asset_list(request):
    qs = AssetItem.objects.filter(is_deleted=False).select_related(
        "asset_type__category", "storage_location"
    ).order_by("asset_tag")

    status = request.GET.get("status", "").strip()
    type_id = request.GET.get("type", "").strip()
    q = request.GET.get("q", "").strip()

    if status:
        qs = qs.filter(status=status)
    if type_id:
        qs = qs.filter(asset_type_id=type_id)
    if q:
        qs = qs.filter(
            Q(asset_tag__icontains=q)
            | Q(brand__icontains=q)
            | Q(model_name__icontains=q)
            | Q(serial_number__icontains=q)
        )

    asset_ids = list(qs.values_list("pk", flat=True))
    active_map = {
        a.asset_id: a
        for a in Assignment.objects.filter(
            asset_id__in=asset_ids,
            returned_at__isnull=True,
        ).select_related("assignee__employee", "assignee__mp", "assignee__office", "assignee__location")
    }

    asset_rows = [(asset, active_map.get(asset.pk)) for asset in qs]

    return render(request, "assets/asset_list.html", {
        "asset_rows": asset_rows,
        "statuses": AssetItem.Status,
        "asset_types": _types_qs(),
        "current_status": status,
        "current_type": type_id,
        "q": q,
    })


@viewer_required
def asset_detail(request, pk):
    asset = get_object_or_404(
        AssetItem.objects.select_related(
            "asset_type__category", "storage_location", "created_by"
        ),
        pk=pk,
        is_deleted=False,
    )

    history = Assignment.objects.filter(asset=asset).select_related(
        "assignee__employee", "assignee__mp", "assignee__office",
        "assignee__location", "performed_by", "batch",
    ).order_by("-assigned_at")

    active_assignment = next((a for a in history if a.returned_at is None), None)

    from lifecycle.models import LifecycleEvent
    lifecycle_events = LifecycleEvent.objects.filter(asset=asset).select_related(
        "performed_by", "component",
    ).order_by("-occurred_at")

    def _expiry_info(expiry_date, purchase_date=None):
        if not expiry_date:
            return None
        today = timezone.now().date()
        days_left = (expiry_date - today).days
        if purchase_date:
            total = max((expiry_date - purchase_date).days, 1)
            elapsed = (today - purchase_date).days
        else:
            total = max((expiry_date - (expiry_date - timedelta(days=730))).days, 1)
            elapsed = 730 - days_left
        pct = min(max(int(elapsed / total * 100), 0), 100)
        if days_left < 0:
            status = "expired"
        elif days_left <= 30:
            status = "danger"
        elif days_left <= 90:
            status = "warning"
        else:
            status = "good"
        return {"days_left": days_left, "pct": pct, "status": status, "expiry": expiry_date}

    warranty_info = _expiry_info(asset.warranty_expiry, asset.purchase_date)
    amc_info = _expiry_info(asset.amc_expiry, asset.purchase_date)

    # Audit timeline (IT Officers and above; rendered conditionally in template)
    from audit.models import AuditLog
    from audit.services import prepare_entries
    audit_entries = prepare_entries(
        AuditLog.objects.filter(
            target_model="assets.AssetItem", target_id=str(asset.pk),
        ).select_related("actor")[:25]
    )

    return render(request, "assets/asset_detail.html", {
        "asset": asset,
        "history": history,
        "active_assignment": active_assignment,
        "components": asset.components.filter(is_active=True),
        "lifecycle_events": lifecycle_events,
        "warranty_info": warranty_info,
        "amc_info": amc_info,
        "audit_entries": audit_entries,
    })


# ---------------------------------------------------------------------------
# Asset CRUD
# ---------------------------------------------------------------------------

@it_officer_required
def asset_create(request):
    categories = AssetCategory.objects.filter(is_active=True)
    types = _types_qs()
    locations = _locations_qs()

    selected_type = None
    spec_schema = []
    form_data = {}
    errors = {}

    raw_type = request.POST.get("asset_type") if request.method == "POST" else request.GET.get("type_id")
    if raw_type:
        try:
            selected_type = AssetType.objects.get(pk=raw_type, is_active=True)
            spec_schema = selected_type.spec_schema or []
        except AssetType.DoesNotExist:
            pass

    if request.method == "POST":
        form_data = request.POST
        errors = _validate_asset_form(request.POST, spec_schema)

        if not errors and selected_type:
            specs = _collect_specs(spec_schema, request.POST)
            tag = request.POST.get("asset_tag", "").strip() or _generate_asset_tag(selected_type)
            work_order = _save_work_order(request)
            asset = AssetItem(
                asset_tag=tag,
                asset_type=selected_type,
                brand=request.POST["brand"].strip(),
                model_name=request.POST["model_name"].strip(),
                serial_number=request.POST.get("serial_number", "").strip(),
                status=AssetItem.Status.IN_STOCK,
                specifications=specs,
                storage_location_id=request.POST.get("storage_location") or None,
                purchase_date=_parse_date_safe(request.POST.get("purchase_date")),
                purchase_order=request.POST.get("purchase_order", "").strip(),
                supplier=request.POST.get("supplier", "").strip(),
                purchase_cost=_parse_decimal_safe(request.POST.get("purchase_cost")),
                warranty_expiry=_parse_date_safe(request.POST.get("warranty_expiry")),
                amc_expiry=_parse_date_safe(request.POST.get("amc_expiry")),
                notes=request.POST.get("notes", "").strip(),
                work_order=work_order,
                created_by=request.user,
            )
            asset.save()
            messages.success(request, f"Asset {asset.asset_tag} created successfully.")
            return redirect("assets:detail", pk=asset.pk)

    if request.method == "POST":
        spec_fields = [(key, _spec_display_value(key, form_data)) for key in spec_schema]
    else:
        spec_fields = [(key, {}) for key in spec_schema]

    return render(request, "assets/asset_form.html", {
        "categories": categories,
        "types": types,
        "locations": locations,
        "selected_type": selected_type,
        "spec_schema": spec_schema,
        "spec_fields": spec_fields,
        "form_data": form_data,
        "errors": errors,
        "form_title": "Add New Asset",
        "is_edit": False,
        **_catalog_context(),
    })


@it_officer_required
def asset_edit(request, pk):
    asset = get_object_or_404(AssetItem, pk=pk, is_deleted=False)
    categories = AssetCategory.objects.filter(is_active=True)
    types = _types_qs()
    locations = _locations_qs()

    errors = {}

    if request.method == "POST":
        raw_type = request.POST.get("asset_type", "")
        try:
            selected_type = AssetType.objects.get(pk=raw_type, is_active=True)
        except AssetType.DoesNotExist:
            selected_type = asset.asset_type
        spec_schema = selected_type.spec_schema or []
        form_data = request.POST
        errors = _validate_asset_form(request.POST, spec_schema, exclude_pk=pk)

        if not errors:
            specs = _collect_specs(spec_schema, request.POST)
            asset.asset_tag = request.POST.get("asset_tag", "").strip() or asset.asset_tag
            asset.asset_type = selected_type
            asset.brand = request.POST["brand"].strip()
            asset.model_name = request.POST["model_name"].strip()
            asset.serial_number = request.POST.get("serial_number", "").strip()
            asset.specifications = specs
            asset.storage_location_id = request.POST.get("storage_location") or None
            asset.purchase_date = _parse_date_safe(request.POST.get("purchase_date"))
            asset.purchase_order = request.POST.get("purchase_order", "").strip()
            asset.supplier = request.POST.get("supplier", "").strip()
            asset.purchase_cost = _parse_decimal_safe(request.POST.get("purchase_cost"))
            asset.warranty_expiry = _parse_date_safe(request.POST.get("warranty_expiry"))
            asset.amc_expiry = _parse_date_safe(request.POST.get("amc_expiry"))
            asset.notes = request.POST.get("notes", "").strip()
            # New work order file replaces the old one; "clear" checkbox removes it
            new_wo = _save_work_order(request)
            if new_wo:
                asset.work_order = new_wo
            elif request.POST.get("clear_work_order"):
                asset.work_order = None
            asset.save()
            messages.success(request, f"Asset {asset.asset_tag} updated.")
            return redirect("assets:detail", pk=asset.pk)
    else:
        selected_type = asset.asset_type
        spec_schema = selected_type.spec_schema or []
        form_data = {
            "asset_tag": asset.asset_tag,
            "asset_type": str(asset.asset_type_id),
            "brand": asset.brand,
            "model_name": asset.model_name,
            "serial_number": asset.serial_number,
            "storage_location": str(asset.storage_location_id) if asset.storage_location_id else "",
            "purchase_date": asset.purchase_date.isoformat() if asset.purchase_date else "",
            "purchase_order": asset.purchase_order,
            "supplier": asset.supplier,
            "purchase_cost": str(asset.purchase_cost) if asset.purchase_cost else "",
            "warranty_expiry": asset.warranty_expiry.isoformat() if asset.warranty_expiry else "",
            "amc_expiry": asset.amc_expiry.isoformat() if asset.amc_expiry else "",
            "notes": asset.notes,
        }

    if request.method == "POST":
        spec_fields = [(key, _spec_display_value(key, form_data)) for key in spec_schema]
    else:
        spec_fields = [(key, asset.specifications.get(key, "")) for key in spec_schema]

    return render(request, "assets/asset_form.html", {
        "asset": asset,
        "categories": categories,
        "types": types,
        "locations": locations,
        "selected_type": selected_type,
        "spec_schema": spec_schema,
        "spec_fields": spec_fields,
        "form_data": form_data,
        "errors": errors,
        "form_title": f"Edit {asset.asset_tag}",
        "is_edit": True,
        **_catalog_context(),
    })


@it_officer_required
def asset_delete(request, pk):
    asset = get_object_or_404(AssetItem, pk=pk, is_deleted=False)
    if request.method == "POST":
        asset.soft_delete()
        from audit.services import record as audit_record
        audit_record("DELETE", asset, note="Soft-deleted")
        messages.success(request, f"Asset {asset.asset_tag} has been deleted.")
        return redirect("assets:list")
    return render(request, "assets/asset_delete_confirm.html", {"asset": asset})


@it_officer_required
def asset_bulk_create(request):
    categories = AssetCategory.objects.filter(is_active=True)
    types = _types_qs()
    locations = _locations_qs()

    selected_type = None
    spec_schema = []
    form_data = {}
    errors = {}
    serial_numbers = []

    raw_type = request.POST.get("asset_type") if request.method == "POST" else request.GET.get("type_id")
    if raw_type:
        try:
            selected_type = AssetType.objects.get(pk=raw_type, is_active=True)
            spec_schema = selected_type.spec_schema or []
        except AssetType.DoesNotExist:
            pass

    if request.method == "POST":
        form_data = request.POST
        errors = _validate_asset_form(request.POST, spec_schema)

        # Validate quantity
        quantity = 0
        try:
            quantity = int(request.POST.get("quantity", 0))
            if quantity < 1:
                errors["quantity"] = "Quantity must be at least 1."
            elif quantity > 500:
                errors["quantity"] = "Maximum 500 assets per bulk add."
        except (ValueError, TypeError):
            errors["quantity"] = "Enter a valid whole number."

        # Parse serial numbers
        raw_serials = request.POST.get("serial_numbers", "").strip()
        serial_numbers = [s.strip() for s in raw_serials.splitlines() if s.strip()]

        if not errors.get("quantity") and quantity > 0:
            if len(serial_numbers) != quantity:
                errors["serial_numbers"] = (
                    f"You entered {len(serial_numbers)} serial number(s) but quantity is {quantity}. "
                    "The count must match exactly."
                )

        if not errors and selected_type:
            specs = _collect_specs(spec_schema, request.POST)
            # One work order shared by all assets in this batch
            shared_work_order = _save_work_order(request)
            created_tags = []
            for serial in serial_numbers:
                tag = _generate_asset_tag(selected_type)
                asset = AssetItem(
                    asset_tag=tag,
                    asset_type=selected_type,
                    brand=request.POST["brand"].strip(),
                    model_name=request.POST["model_name"].strip(),
                    serial_number=serial,
                    status=AssetItem.Status.IN_STOCK,
                    specifications=specs,
                    storage_location_id=request.POST.get("storage_location") or None,
                    purchase_date=_parse_date_safe(request.POST.get("purchase_date")),
                    purchase_order=request.POST.get("purchase_order", "").strip(),
                    supplier=request.POST.get("supplier", "").strip(),
                    purchase_cost=_parse_decimal_safe(request.POST.get("purchase_cost")),
                    warranty_expiry=_parse_date_safe(request.POST.get("warranty_expiry")),
                    amc_expiry=_parse_date_safe(request.POST.get("amc_expiry")),
                    notes=request.POST.get("notes", "").strip(),
                    work_order=shared_work_order,
                    created_by=request.user,
                )
                asset.save()
                created_tags.append(tag)

            messages.success(request, f"Bulk add complete: {len(created_tags)} asset(s) created successfully.")
            return redirect("assets:list")

    if request.method == "POST":
        spec_fields = [(key, _spec_display_value(key, form_data)) for key in spec_schema]
    else:
        spec_fields = [(key, {}) for key in spec_schema]

    return render(request, "assets/bulk_add.html", {
        "categories": categories,
        "types": types,
        "locations": locations,
        "selected_type": selected_type,
        "spec_schema": spec_schema,
        "spec_fields": spec_fields,
        "form_data": form_data,
        "errors": errors,
        "serial_numbers_raw": request.POST.get("serial_numbers", "") if request.method == "POST" else "",
        **_catalog_context(),
    })


@viewer_required
def asset_spec_fields(request):
    """HTMX endpoint: returns spec fields partial when asset type changes."""
    type_id = request.GET.get("asset_type") or request.GET.get("type_id")
    spec_schema = []
    if type_id:
        try:
            asset_type = AssetType.objects.get(pk=type_id)
            spec_schema = asset_type.spec_schema or []
        except AssetType.DoesNotExist:
            pass
    spec_fields = [(key, {}) for key in spec_schema]
    choices = {}
    for sc in SpecChoice.objects.filter(is_active=True).order_by("spec_key", "order", "label"):
        choices.setdefault(sc.spec_key, []).append((sc.value, sc.display_label()))
    return render(request, "assets/partials/spec_fields.html", {
        "spec_fields": spec_fields,
        "spec_choices_by_key": choices,
    })


@viewer_required
def work_order_serve(request, pk):
    """Serve a work order document (login required; never direct media URL)."""
    import mimetypes
    from django.http import FileResponse
    wo = WorkOrder.objects.get(pk=pk)
    mime, _ = mimetypes.guess_type(wo.document.name)
    mime = mime or "application/octet-stream"
    # Inline for PDF/images so the browser renders them; force download otherwise
    disposition = "inline" if mime in ("application/pdf", "image/jpeg", "image/png") else "attachment"
    response = FileResponse(wo.document.open("rb"), content_type=mime)
    response["Content-Disposition"] = f'{disposition}; filename="{wo.filename}"'
    return response


@viewer_required
def asset_history_print(request, pk):
    asset = get_object_or_404(
        AssetItem.objects.select_related("asset_type__category", "storage_location"),
        pk=pk, is_deleted=False,
    )
    history = list(
        Assignment.objects.filter(asset=asset)
        .select_related("assignee", "assignee__employee", "assignee__mp",
                        "assignee__office", "assignee__location", "performed_by")
        .order_by("assigned_at")
    )
    active_assignment = next((a for a in history if a.returned_at is None), None)
    return render(request, "print/history_print.html", {
        "page_title": f"Assignment History — {asset.asset_tag}",
        "asset": asset,
        "active_assignment": active_assignment,
        "history": history,
        "generated_at": timezone.now(),
    })


@viewer_required
def asset_tag_check(request):
    """HTMX live validation: checks if an asset tag is already in use."""
    tag = request.GET.get("asset_tag", "").strip()
    exclude_pk = request.GET.get("exclude_pk", "").strip()
    if not tag:
        return HttpResponse("")
    qs = AssetItem.objects.filter(asset_tag=tag)
    if exclude_pk.isdigit():
        qs = qs.exclude(pk=int(exclude_pk))
    if qs.exists():
        return HttpResponse(
            '<span style="color:#EF4444;font-size:11px;font-weight:600">✗ Tag already in use</span>'
        )
    return HttpResponse(
        '<span style="color:#10B981;font-size:11px;font-weight:600">✓ Available</span>'
    )


# ---------------------------------------------------------------------------
# Excel Import
# ---------------------------------------------------------------------------

@it_officer_required
def import_template(request):
    type_id = request.GET.get("type_id", "").strip()
    if not type_id:
        return redirect("assets:import_upload")
    try:
        wb = ExcelTemplateGenerator().generate_template(int(type_id))
        asset_type = AssetType.objects.get(pk=type_id)
    except (AssetType.DoesNotExist, ValueError):
        messages.error(request, "Invalid asset type.")
        return redirect("assets:import_upload")

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"import_template_{re.sub(r'[^A-Za-z0-9]', '_', asset_type.name)}.xlsx"
    return HttpResponse(
        buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@it_officer_required
def import_upload(request):
    types = _types_qs()

    if request.method == "POST":
        type_id = request.POST.get("asset_type", "").strip()
        uploaded = request.FILES.get("excel_file")

        upload_errors = []
        if not type_id:
            upload_errors.append("Please select an asset type.")
        if not uploaded:
            upload_errors.append("Please select an Excel file to upload.")

        if not upload_errors:
            try:
                validated_rows = ExcelImportValidator().validate(uploaded, int(type_id))
            except ValueError as e:
                upload_errors.append(str(e))
                validated_rows = []

            if not upload_errors:
                request.session[SESSION_KEY_ROWS] = validated_rows
                request.session[SESSION_KEY_TYPE] = int(type_id)
                request.session.modified = True

                try:
                    asset_type = AssetType.objects.select_related("category").get(pk=type_id)
                except AssetType.DoesNotExist:
                    messages.error(request, "Invalid asset type.")
                    return redirect("assets:import_upload")

                valid_count = sum(1 for r in validated_rows if r["status"] in ("valid", "warning"))
                error_count = sum(1 for r in validated_rows if r["status"] == "error")

                return render(request, "assets/import_preview.html", {
                    "rows": validated_rows,
                    "asset_type": asset_type,
                    "valid_count": valid_count,
                    "error_count": error_count,
                    "total_count": len(validated_rows),
                })

        return render(request, "assets/import_upload.html", {
            "types": types,
            "upload_errors": upload_errors,
        })

    return render(request, "assets/import_upload.html", {"types": types})


@it_officer_required
def import_confirm(request):
    if request.method != "POST":
        return redirect("assets:import_upload")

    validated_rows = request.session.get(SESSION_KEY_ROWS)
    type_id = request.session.get(SESSION_KEY_TYPE)

    if not validated_rows or not type_id:
        messages.error(request, "Import session expired. Please re-upload the file.")
        return redirect("assets:import_upload")

    result = ExcelImportExecutor().execute(validated_rows, type_id, request.user)

    request.session.pop(SESSION_KEY_ROWS, None)
    request.session.pop(SESSION_KEY_TYPE, None)
    request.session.pop(SESSION_KEY_COLS, None)

    if result["errors"]:
        messages.error(request, f"Import failed: {result['errors'][0]}")
        return redirect("assets:import_upload")

    msg = f"Import complete: {result['created']} asset(s) created."
    if result["skipped"]:
        msg += f" {result['skipped']} row(s) with errors were skipped."
    messages.success(request, msg)
    return redirect("assets:list")
