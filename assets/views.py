import io
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from assignments.models import Assignment, AlertStatus, InactiveHolderAlert
from config.permissions import it_officer_required, viewer_required
from locations.models import Location

from .models import AssetCategory, AssetItem, AssetType
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


# ---------------------------------------------------------------------------
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
    issues_count = qs.filter(
        status__in=[
            AssetItem.Status.MAINTENANCE,
            AssetItem.Status.LOST,
            AssetItem.Status.DAMAGED,
        ]
    ).count()

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

    return render(request, "dashboard.html", {
        "total": total,
        "assigned_count": assigned_count,
        "in_stock_count": in_stock_count,
        "issues_count": issues_count,
        "expiring_assets": expiring_assets,
        "open_alerts": open_alerts,
        "recent_assignments": recent_assignments,
        "recent_events": recent_events,
        "last_sync": last_sync,
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
        ).select_related("assignee__employee", "assignee__mp", "assignee__office")
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

    return render(request, "assets/asset_detail.html", {
        "asset": asset,
        "history": history,
        "active_assignment": active_assignment,
        "components": asset.components.filter(is_active=True),
        "lifecycle_events": lifecycle_events,
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
            specs = {key: request.POST.get(f"spec_{key}", "") for key in spec_schema}
            tag = request.POST.get("asset_tag", "").strip() or _generate_asset_tag(selected_type)
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
                created_by=request.user,
            )
            asset.save()
            messages.success(request, f"Asset {asset.asset_tag} created successfully.")
            return redirect("assets:detail", pk=asset.pk)

    spec_fields = [(key, form_data.get(f"spec_{key}", "")) for key in spec_schema]

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
            specs = {key: request.POST.get(f"spec_{key}", "") for key in spec_schema}
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

    spec_fields = [(key, form_data.get(f"spec_{key}", "") if request.method == "POST" else asset.specifications.get(key, "")) for key in spec_schema]

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
    })


@it_officer_required
def asset_delete(request, pk):
    asset = get_object_or_404(AssetItem, pk=pk, is_deleted=False)
    if request.method == "POST":
        asset.soft_delete()
        messages.success(request, f"Asset {asset.asset_tag} has been deleted.")
        return redirect("assets:list")
    return render(request, "assets/asset_delete_confirm.html", {"asset": asset})


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
    spec_fields = [(key, "") for key in spec_schema]
    return render(request, "assets/partials/spec_fields.html", {"spec_fields": spec_fields})


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
