"""
Parliament IT Inventory — Reports views.

Viewers and above can download all reports. PDF downloads also require
viewer_required since they contain sensitive asset/holder data.
"""

import urllib.parse
from datetime import date, datetime, timedelta

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

from config.permissions import viewer_required
from reports.columns import (
    ASSET_HISTORY_COLS,
    HOLDER_ASSIGNMENTS_COLS,
    INVENTORY_COLS,
    LIFECYCLE_COLS,
    TRANSFER_LOG_COLS,
    WARRANTY_COLS,
    parse_cols,
)
from reports.generators.excel import (
    asset_history_excel,
    holder_assignments_excel,
    inventory_excel,
    lifecycle_events_excel,
    transfer_log_excel,
    warranty_expiry_excel,
)
from reports.generators.pdf import disposal_pdf, handover_pdf, tabular_pdf


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _date_str(d) -> str:
    if d is None:
        return ""
    return d.strftime("%d %b %Y") if hasattr(d, "strftime") else str(d)


def _dt_str(dt) -> str:
    if dt is None:
        return ""
    return dt.strftime("%d %b %Y %H:%M") if hasattr(dt, "strftime") else str(dt)


from django.http import HttpResponse


def _excel_response(data: bytes, filename: str) -> HttpResponse:
    resp = HttpResponse(
        data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


def _pdf_response(data: bytes, filename: str) -> HttpResponse:
    resp = HttpResponse(data, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


def _strip_params(request, *exclude_keys: str) -> str:
    """Build a URL query string from current GET params, excluding given keys."""
    params = [(k, v) for k, v in request.GET.items() if k not in exclude_keys]
    return urllib.parse.urlencode(params)


def _parse_per_page(request, default: int = 50) -> int:
    try:
        per_page = int(request.GET.get("per_page", default))
        return per_page if per_page in (25, 50, 100) else default
    except (ValueError, TypeError):
        return default


# ── Report index ───────────────────────────────────────────────────────────────

@viewer_required
def report_index(request):
    return render(request, "reports/index.html")


# ── View pages (Session 8.2) ───────────────────────────────────────────────────

@viewer_required
def view_inventory(request):
    from assets.models import AssetCategory, AssetItem, AssetType
    from assignments.models import Assignment

    # Filters
    status      = request.GET.get("status") or ""
    category    = request.GET.get("category") or ""
    type_       = request.GET.get("type") or ""
    ram_type    = request.GET.get("ram_type") or ""
    os_name     = request.GET.get("os_name") or ""
    os_licensed = request.GET.get("os_licensed") or ""

    # Column selection
    selected_keys = parse_cols(request, INVENTORY_COLS)
    label_map     = dict(INVENTORY_COLS)
    selected_cols = [(k, label_map[k]) for k in selected_keys]

    # Pagination
    per_page  = _parse_per_page(request)
    page_num  = request.GET.get("page", 1)

    # Queryset
    qs = AssetItem.objects.filter(is_deleted=False).select_related(
        "asset_type__category", "storage_location",
    ).order_by("asset_tag")

    if status:
        qs = qs.filter(status=status)
    if category:
        qs = qs.filter(asset_type__category_id=category)
    if type_:
        qs = qs.filter(asset_type_id=type_)
    if ram_type:
        qs = qs.filter(specifications__ram__type=ram_type)
    if os_name:
        qs = qs.filter(specifications__os__name=os_name)
    if os_licensed:
        qs = qs.filter(specifications__os__licensed=os_licensed)

    paginator = Paginator(qs, per_page)
    page_obj  = paginator.get_page(page_num)

    # Active assignment map — only for assets on this page
    page_pks = [a.pk for a in page_obj]
    active_map = {
        asgn.asset_id: asgn
        for asgn in Assignment.objects.filter(
            asset_id__in=page_pks, returned_at__isnull=True,
        ).select_related("assignee__employee", "assignee__mp", "assignee__office")
    }

    # Build rows as list of dicts (includes private _keys for template rendering)
    rows = []
    for asset in page_obj:
        asgn = active_map.get(asset.pk)
        holder = asgn.assignee.display_name if asgn else ""
        htype  = asgn.assignee.get_assignee_type_display() if asgn else ""
        since  = _date_str(asgn.assigned_at.date()) if asgn else ""
        rows.append({
            "_pk":          asset.pk,
            "_detail_url":  reverse("assets:detail", args=[asset.pk]),
            "_status_raw":  asset.status,
            "asset_tag":        asset.asset_tag,
            "category":         asset.asset_type.category.name,
            "type":             asset.asset_type.name,
            "brand":            asset.brand,
            "model":            asset.model_name,
            "serial_no":        asset.serial_number or "",
            "status":           asset.get_status_display(),
            "storage_location": asset.storage_location.full_path if asset.storage_location else "",
            "current_holder":   holder,
            "holder_type":      htype,
            "assigned_since":   since,
            "purchase_date":    _date_str(asset.purchase_date),
            "warranty_expiry":  _date_str(asset.warranty_expiry),
            "amc_expiry":       _date_str(asset.amc_expiry),
        })

    # Filter dropdown data
    categories = AssetCategory.objects.filter(is_active=True).order_by("name")
    types = AssetType.objects.filter(is_active=True).select_related("category").order_by("name")
    if category:
        types = types.filter(category_id=category)

    return render(request, "reports/view_inventory.html", {
        "rows":             rows,
        "selected_cols":    selected_cols,
        "selected_col_keys": selected_keys,
        "all_cols":         INVENTORY_COLS,
        "page_obj":         page_obj,
        "per_page":         per_page,
        "start_index":      page_obj.start_index(),
        "total_count":      paginator.count,
        "status":           status,
        "category":         category,
        "type":             type_,
        "ram_type":         ram_type,
        "os_name":          os_name,
        "os_licensed":      os_licensed,
        "categories":       categories,
        "types":            types,
        "status_choices":   AssetItem.Status.choices,
        "base_qs":          _strip_params(request, "page"),
        "base_qs_nopag":    _strip_params(request, "page", "per_page"),
    })


@viewer_required
def view_holder_assignments(request):
    from assignments.models import Assignment
    from assignees.models import AssigneeType

    # Filter
    holder_type = request.GET.get("holder_type") or ""

    # Column selection
    selected_keys = parse_cols(request, HOLDER_ASSIGNMENTS_COLS)
    label_map     = dict(HOLDER_ASSIGNMENTS_COLS)
    selected_cols = [(k, label_map[k]) for k in selected_keys]

    # Pagination
    per_page = _parse_per_page(request)
    page_num = request.GET.get("page", 1)

    # Queryset
    qs = (
        Assignment.objects.filter(returned_at__isnull=True)
        .select_related(
            "asset__asset_type__category",
            "assignee__employee", "assignee__mp", "assignee__office",
        )
        .order_by(
            "assignee__assignee_type",
            "assignee__employee__name_en",
            "assignee__mp__name_en",
            "assignee__office__name_en",
            "asset__asset_tag",
        )
    )

    if holder_type in (t.value for t in AssigneeType):
        qs = qs.filter(assignee__assignee_type=holder_type)

    paginator = Paginator(qs, per_page)
    page_obj  = paginator.get_page(page_num)

    rows = []
    for asgn in page_obj:
        snap = asgn.holder_snapshot or {}
        rows.append({
            "_detail_url":  reverse("assets:detail", args=[asgn.asset.pk]),
            "_status_raw":  asgn.asset.status,
            "holder":        asgn.assignee.display_name,
            "holder_type":   asgn.assignee.get_assignee_type_display(),
            "designation":   snap.get("designation", ""),
            "department":    snap.get("department", ""),
            "asset_tag":     asgn.asset.asset_tag,
            "category":      asgn.asset.asset_type.category.name,
            "asset_type":    asgn.asset.asset_type.name,
            "brand":         asgn.asset.brand,
            "model":         asgn.asset.model_name,
            "status":        asgn.asset.get_status_display(),
            "assigned_since": _date_str(asgn.assigned_at.date()),
        })

    return render(request, "reports/view_holder_assignments.html", {
        "rows":              rows,
        "selected_cols":     selected_cols,
        "selected_col_keys": selected_keys,
        "all_cols":          HOLDER_ASSIGNMENTS_COLS,
        "page_obj":          page_obj,
        "per_page":          per_page,
        "start_index":       page_obj.start_index(),
        "total_count":       paginator.count,
        "holder_type":       holder_type,
        "holder_type_choices": [(t.value, t.label) for t in AssigneeType],
        "base_qs":           _strip_params(request, "page"),
        "base_qs_nopag":     _strip_params(request, "page", "per_page"),
    })


@viewer_required
def view_transfer_log(request):
    from assignments.models import Assignment

    # Filters
    date_from = _parse_date(request.GET.get("date_from"))
    date_to   = _parse_date(request.GET.get("date_to"))

    # Column selection
    selected_keys = parse_cols(request, TRANSFER_LOG_COLS)
    label_map     = dict(TRANSFER_LOG_COLS)
    selected_cols = [(k, label_map[k]) for k in selected_keys]

    # Pagination
    per_page = _parse_per_page(request)
    page_num = request.GET.get("page", 1)

    # Queryset
    qs = Assignment.objects.select_related(
        "asset__asset_type__category",
        "assignee__employee", "assignee__mp", "assignee__office",
        "performed_by", "batch",
    ).order_by("-assigned_at")

    if date_from:
        qs = qs.filter(assigned_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(assigned_at__date__lte=date_to)

    # Cap at 5000 — convert to list to allow Paginator to work on sliced data
    total_raw = qs.count()
    capped    = total_raw >= 5000
    paginator = Paginator(list(qs[:5000]) if capped else qs, per_page)
    page_obj  = paginator.get_page(page_num)

    rows = []
    for asgn in page_obj:
        snap = asgn.holder_snapshot or {}
        rows.append({
            "_detail_url": reverse("assets:detail", args=[asgn.asset.pk]),
            "_is_active":  asgn.returned_at is None,
            "transfer_date": _dt_str(asgn.assigned_at),
            "asset_tag":   asgn.asset.asset_tag,
            "category":    asgn.asset.asset_type.category.name,
            "type":        asgn.asset.asset_type.name,
            "brand":       asgn.asset.brand,
            "model":       asgn.asset.model_name,
            "assigned_to": snap.get("display_name", ""),
            "holder_type": snap.get("assignee_type", ""),
            "designation": snap.get("designation", ""),
            "status": "Active" if asgn.returned_at is None else f"Returned {_date_str(asgn.returned_at.date())}",
            "performed_by": asgn.performed_by.get_full_name() or asgn.performed_by.username,
            "batch_ref":   asgn.batch.reference if asgn.batch_id else "",
            "notes":       asgn.notes or "",
        })

    return render(request, "reports/view_transfer_log.html", {
        "rows":              rows,
        "selected_cols":     selected_cols,
        "selected_col_keys": selected_keys,
        "all_cols":          TRANSFER_LOG_COLS,
        "page_obj":          page_obj,
        "per_page":          per_page,
        "start_index":       page_obj.start_index(),
        "total_count":       paginator.count,
        "capped":            capped,
        "date_from":         date_from,
        "date_to":           date_to,
        "base_qs":           _strip_params(request, "page"),
        "base_qs_nopag":     _strip_params(request, "page", "per_page"),
    })


@viewer_required
def view_lifecycle(request):
    from assets.models import AssetItem
    from lifecycle.models import EventType, LifecycleEvent

    # Filters
    date_from  = _parse_date(request.GET.get("date_from"))
    date_to    = _parse_date(request.GET.get("date_to"))
    event_type = request.GET.get("event_type") or ""

    # Column selection
    selected_keys = parse_cols(request, LIFECYCLE_COLS)
    label_map     = dict(LIFECYCLE_COLS)
    selected_cols = [(k, label_map[k]) for k in selected_keys]

    # Pagination
    per_page = _parse_per_page(request)
    page_num = request.GET.get("page", 1)

    # Queryset
    qs = LifecycleEvent.objects.select_related(
        "asset__asset_type__category", "performed_by",
    ).order_by("-occurred_at")

    if date_from:
        qs = qs.filter(occurred_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(occurred_at__date__lte=date_to)
    if event_type:
        qs = qs.filter(event_type=event_type)

    # Cap at 5000
    total_raw = qs.count()
    capped    = total_raw >= 5000
    paginator = Paginator(list(qs[:5000]) if capped else qs, per_page)
    page_obj  = paginator.get_page(page_num)

    rows = []
    for ev in page_obj:
        try:
            old_label = AssetItem.Status(ev.old_status).label
            old_raw   = ev.old_status
        except (ValueError, KeyError):
            old_label = ev.old_status or ""
            old_raw   = ""
        try:
            new_label = AssetItem.Status(ev.new_status).label
            new_raw   = ev.new_status
        except (ValueError, KeyError):
            new_label = ev.new_status or ""
            new_raw   = ""

        rows.append({
            "_detail_url":     reverse("assets:detail", args=[ev.asset.pk]),
            "_old_status_raw": old_raw,
            "_new_status_raw": new_raw,
            "date":        _dt_str(ev.occurred_at),
            "asset_tag":   ev.asset.asset_tag,
            "category":    ev.asset.asset_type.category.name,
            "type":        ev.asset.asset_type.name,
            "brand":       ev.asset.brand,
            "model":       ev.asset.model_name,
            "event":       ev.get_event_type_display(),
            "old_status":  old_label,
            "new_status":  new_label,
            "notes":       ev.note or "",
            "performed_by": ev.performed_by.get_full_name() or ev.performed_by.username,
        })

    return render(request, "reports/view_lifecycle.html", {
        "rows":              rows,
        "selected_cols":     selected_cols,
        "selected_col_keys": selected_keys,
        "all_cols":          LIFECYCLE_COLS,
        "page_obj":          page_obj,
        "per_page":          per_page,
        "start_index":       page_obj.start_index(),
        "total_count":       paginator.count,
        "capped":            capped,
        "date_from":         date_from,
        "date_to":           date_to,
        "event_type":        event_type,
        "event_type_choices": [(t.value, t.label) for t in EventType],
        "base_qs":           _strip_params(request, "page"),
        "base_qs_nopag":     _strip_params(request, "page", "per_page"),
    })


# ── PDF download views (Session 8.2 + 8.3) ───────────────────────────────────

@viewer_required
def download_inventory_pdf(request):
    from assets.models import AssetItem
    from assignments.models import Assignment

    filters  = {k: request.GET.get(k) for k in ("status", "category", "type") if request.GET.get(k)}
    sel_keys = parse_cols(request, INVENTORY_COLS)
    labels   = [dict(INVENTORY_COLS)[k] for k in sel_keys]

    qs = AssetItem.objects.filter(is_deleted=False).select_related(
        "asset_type__category", "storage_location",
    ).order_by("asset_tag")

    if filters.get("status"):
        qs = qs.filter(status=filters["status"])
    if filters.get("category"):
        qs = qs.filter(asset_type__category_id=filters["category"])
    if filters.get("type"):
        qs = qs.filter(asset_type_id=filters["type"])
    if request.GET.get("ram_type"):
        qs = qs.filter(specifications__ram__type=request.GET["ram_type"])
    if request.GET.get("os_name"):
        qs = qs.filter(specifications__os__name=request.GET["os_name"])
    if request.GET.get("os_licensed"):
        qs = qs.filter(specifications__os__licensed=request.GET["os_licensed"])

    qs = list(qs[:5000])
    pks = [a.pk for a in qs]
    active_map = {
        asgn.asset_id: asgn
        for asgn in Assignment.objects.filter(
            asset_id__in=pks, returned_at__isnull=True,
        ).select_related("assignee__employee", "assignee__mp", "assignee__office")
    }

    rows = []
    for asset in qs:
        asgn   = active_map.get(asset.pk)
        holder = asgn.assignee.display_name if asgn else ""
        htype  = asgn.assignee.get_assignee_type_display() if asgn else ""
        since  = _date_str(asgn.assigned_at.date()) if asgn else ""
        rd = {
            "asset_tag":        asset.asset_tag,
            "category":         asset.asset_type.category.name,
            "type":             asset.asset_type.name,
            "brand":            asset.brand,
            "model":            asset.model_name,
            "serial_no":        asset.serial_number or "",
            "status":           asset.get_status_display(),
            "storage_location": asset.storage_location.full_path if asset.storage_location else "",
            "current_holder":   holder,
            "holder_type":      htype,
            "assigned_since":   since,
            "purchase_date":    _date_str(asset.purchase_date),
            "warranty_expiry":  _date_str(asset.warranty_expiry),
            "amc_expiry":       _date_str(asset.amc_expiry),
        }
        rows.append([rd[k] for k in sel_keys])

    data = tabular_pdf(
        title="Current IT Asset Inventory",
        subtitle=f"Generated: {_date_str(date.today())}",
        column_labels=labels,
        rows=rows,
        generated_at=timezone.now(),
    )
    return _pdf_response(data, f"inventory_{date.today():%Y%m%d}.pdf")


@viewer_required
def download_holder_assignments_pdf(request):
    from assignments.models import Assignment
    from assignees.models import AssigneeType

    holder_type = request.GET.get("holder_type") or None
    sel_keys    = parse_cols(request, HOLDER_ASSIGNMENTS_COLS)
    labels      = [dict(HOLDER_ASSIGNMENTS_COLS)[k] for k in sel_keys]

    qs = (
        Assignment.objects.filter(returned_at__isnull=True)
        .select_related(
            "asset__asset_type__category",
            "assignee__employee", "assignee__mp", "assignee__office",
        )
        .order_by(
            "assignee__assignee_type",
            "assignee__employee__name_en",
            "assignee__mp__name_en",
            "assignee__office__name_en",
            "asset__asset_tag",
        )
    )

    if holder_type in (t.value for t in AssigneeType):
        qs = qs.filter(assignee__assignee_type=holder_type)

    subtitle = f"Holder type: {holder_type}" if holder_type else "All holder types"

    rows = []
    for asgn in qs[:5000]:
        snap = asgn.holder_snapshot or {}
        rd = {
            "holder":        asgn.assignee.display_name,
            "holder_type":   asgn.assignee.get_assignee_type_display(),
            "designation":   snap.get("designation", ""),
            "department":    snap.get("department", ""),
            "asset_tag":     asgn.asset.asset_tag,
            "category":      asgn.asset.asset_type.category.name,
            "asset_type":    asgn.asset.asset_type.name,
            "brand":         asgn.asset.brand,
            "model":         asgn.asset.model_name,
            "status":        asgn.asset.get_status_display(),
            "assigned_since": _date_str(asgn.assigned_at.date()),
        }
        rows.append([rd[k] for k in sel_keys])

    data = tabular_pdf(
        title="Current Holder Assignments",
        subtitle=subtitle,
        column_labels=labels,
        rows=rows,
        generated_at=timezone.now(),
    )
    return _pdf_response(data, f"holder_assignments_{date.today():%Y%m%d}.pdf")


@viewer_required
def download_transfer_log_pdf(request):
    from assignments.models import Assignment

    date_from = _parse_date(request.GET.get("date_from"))
    date_to   = _parse_date(request.GET.get("date_to"))
    sel_keys  = parse_cols(request, TRANSFER_LOG_COLS)
    labels    = [dict(TRANSFER_LOG_COLS)[k] for k in sel_keys]

    qs = Assignment.objects.select_related(
        "asset__asset_type__category",
        "assignee__employee", "assignee__mp", "assignee__office",
        "performed_by", "batch",
    ).order_by("-assigned_at")

    if date_from:
        qs = qs.filter(assigned_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(assigned_at__date__lte=date_to)

    subtitle = ""
    if date_from or date_to:
        d1 = _date_str(date_from) if date_from else "Start"
        d2 = _date_str(date_to)   if date_to   else "Today"
        subtitle = f"Period: {d1} – {d2}"

    rows = []
    for asgn in qs[:5000]:
        snap = asgn.holder_snapshot or {}
        status_str = "Active" if asgn.returned_at is None else f"Returned {_date_str(asgn.returned_at.date())}"
        rd = {
            "transfer_date": _dt_str(asgn.assigned_at),
            "asset_tag":   asgn.asset.asset_tag,
            "category":    asgn.asset.asset_type.category.name,
            "type":        asgn.asset.asset_type.name,
            "brand":       asgn.asset.brand,
            "model":       asgn.asset.model_name,
            "assigned_to": snap.get("display_name", ""),
            "holder_type": snap.get("assignee_type", ""),
            "designation": snap.get("designation", ""),
            "status":      status_str,
            "performed_by": asgn.performed_by.get_full_name() or asgn.performed_by.username,
            "batch_ref":   asgn.batch.reference if asgn.batch_id else "",
            "notes":       asgn.notes or "",
        }
        rows.append([rd[k] for k in sel_keys])

    data = tabular_pdf(
        title="Asset Transfer Log",
        subtitle=subtitle,
        column_labels=labels,
        rows=rows,
        generated_at=timezone.now(),
    )
    return _pdf_response(data, f"transfer_log_{date.today():%Y%m%d}.pdf")


@viewer_required
def download_lifecycle_pdf(request):
    from assets.models import AssetItem
    from lifecycle.models import LifecycleEvent

    date_from  = _parse_date(request.GET.get("date_from"))
    date_to    = _parse_date(request.GET.get("date_to"))
    event_type = request.GET.get("event_type") or None
    sel_keys   = parse_cols(request, LIFECYCLE_COLS)
    labels     = [dict(LIFECYCLE_COLS)[k] for k in sel_keys]

    qs = LifecycleEvent.objects.select_related(
        "asset__asset_type__category", "performed_by",
    ).order_by("-occurred_at")

    if date_from:
        qs = qs.filter(occurred_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(occurred_at__date__lte=date_to)
    if event_type:
        qs = qs.filter(event_type=event_type)

    rows = []
    for ev in qs[:5000]:
        try:
            old_label = AssetItem.Status(ev.old_status).label
        except (ValueError, KeyError):
            old_label = ev.old_status or ""
        try:
            new_label = AssetItem.Status(ev.new_status).label
        except (ValueError, KeyError):
            new_label = ev.new_status or ""

        rd = {
            "date":        _dt_str(ev.occurred_at),
            "asset_tag":   ev.asset.asset_tag,
            "category":    ev.asset.asset_type.category.name,
            "type":        ev.asset.asset_type.name,
            "brand":       ev.asset.brand,
            "model":       ev.asset.model_name,
            "event":       ev.get_event_type_display(),
            "old_status":  old_label,
            "new_status":  new_label,
            "notes":       ev.note or "",
            "performed_by": ev.performed_by.get_full_name() or ev.performed_by.username,
        }
        rows.append([rd[k] for k in sel_keys])

    data = tabular_pdf(
        title="Lifecycle Events Log",
        subtitle="",
        column_labels=labels,
        rows=rows,
        generated_at=timezone.now(),
    )
    return _pdf_response(data, f"lifecycle_events_{date.today():%Y%m%d}.pdf")


@viewer_required
def view_warranty(request):
    from assets.models import AssetItem
    from assignments.models import Assignment
    from django.db.models import Q

    # Filter
    try:
        days = int(request.GET.get("days", 90))
        days = max(1, min(days, 3650))
    except (ValueError, TypeError):
        days = 90

    # Column selection
    selected_keys = parse_cols(request, WARRANTY_COLS)
    label_map     = dict(WARRANTY_COLS)
    selected_cols = [(k, label_map[k]) for k in selected_keys]

    # Pagination
    per_page = _parse_per_page(request)
    page_num = request.GET.get("page", 1)

    today   = date.today()
    horizon = today + timedelta(days=days)

    qs = AssetItem.objects.filter(
        is_deleted=False,
    ).filter(
        Q(warranty_expiry__lte=horizon) | Q(amc_expiry__lte=horizon)
    ).select_related("asset_type__category").order_by("warranty_expiry", "amc_expiry")

    paginator = Paginator(qs, per_page)
    page_obj  = paginator.get_page(page_num)

    # Active assignment map for this page only
    page_pks = [a.pk for a in page_obj]
    active_map = {
        asgn.asset_id: asgn
        for asgn in Assignment.objects.filter(
            asset_id__in=page_pks, returned_at__isnull=True,
        ).select_related("assignee__employee", "assignee__mp", "assignee__office")
    }

    def _days_color(d):
        if d is None:
            return ""
        return "days-expired" if d <= 0 else ("days-soon" if d <= 30 else "")

    rows = []
    for asset in page_obj:
        asgn  = active_map.get(asset.pk)
        holder = asgn.assignee.display_name if asgn else ""
        wty_d  = (asset.warranty_expiry - today).days if asset.warranty_expiry else None
        amc_d  = (asset.amc_expiry      - today).days if asset.amc_expiry      else None
        rows.append({
            "_detail_url":            reverse("assets:detail", args=[asset.pk]),
            "_status_raw":            asset.status,
            "_warranty_days_color":   _days_color(wty_d),
            "_amc_days_color":        _days_color(amc_d),
            "asset_tag":      asset.asset_tag,
            "category":       asset.asset_type.category.name,
            "type":           asset.asset_type.name,
            "brand":          asset.brand,
            "model":          asset.model_name,
            "status":         asset.get_status_display(),
            "current_holder": holder,
            "warranty_expiry": _date_str(asset.warranty_expiry),
            "warranty_days":  "" if wty_d is None else wty_d,
            "amc_expiry":     _date_str(asset.amc_expiry),
            "amc_days":       "" if amc_d is None else amc_d,
        })

    return render(request, "reports/view_warranty.html", {
        "rows":              rows,
        "selected_cols":     selected_cols,
        "selected_col_keys": selected_keys,
        "all_cols":          WARRANTY_COLS,
        "page_obj":          page_obj,
        "per_page":          per_page,
        "start_index":       page_obj.start_index(),
        "total_count":       paginator.count,
        "days":              days,
        "base_qs":           _strip_params(request, "page"),
        "base_qs_nopag":     _strip_params(request, "page", "per_page"),
    })


@viewer_required
def view_asset_history(request, pk: int):
    from assets.models import AssetItem
    from assignments.models import Assignment

    asset = get_object_or_404(AssetItem, pk=pk, is_deleted=False)

    # Column selection
    selected_keys = parse_cols(request, ASSET_HISTORY_COLS)
    label_map     = dict(ASSET_HISTORY_COLS)
    selected_cols = [(k, label_map[k]) for k in selected_keys]

    # Full history — no pagination (rarely > 100 rows per asset)
    history = Assignment.objects.filter(asset=asset).select_related(
        "performed_by", "batch",
    ).order_by("-assigned_at")

    rows = []
    for asgn in history:
        snap = asgn.holder_snapshot or {}
        if asgn.returned_at:
            to_date   = _date_str(asgn.returned_at.date())
            days_held = (asgn.returned_at - asgn.assigned_at).days
        else:
            to_date   = "Current"
            days_held = (timezone.now() - asgn.assigned_at).days
        rows.append({
            "assigned_to":  snap.get("display_name", ""),
            "holder_type":  snap.get("assignee_type", ""),
            "designation":  snap.get("designation", ""),
            "department":   snap.get("department", ""),
            "from_date":    _date_str(asgn.assigned_at.date()),
            "to_date":      to_date,
            "days":         days_held,
            "performed_by": asgn.performed_by.get_full_name() or asgn.performed_by.username,
            "batch_ref":    asgn.batch.reference if asgn.batch_id else "",
            "notes":        asgn.notes or "",
        })

    return render(request, "reports/view_asset_history.html", {
        "asset":             asset,
        "rows":              rows,
        "selected_cols":     selected_cols,
        "selected_col_keys": selected_keys,
        "all_cols":          ASSET_HISTORY_COLS,
        "total_count":       len(rows),
    })


@viewer_required
def download_warranty_pdf(request):
    from assets.models import AssetItem
    from assignments.models import Assignment
    from django.db.models import Q

    try:
        days = int(request.GET.get("days", 90))
        days = max(1, min(days, 3650))
    except (ValueError, TypeError):
        days = 90

    sel_keys = parse_cols(request, WARRANTY_COLS)
    labels   = [dict(WARRANTY_COLS)[k] for k in sel_keys]

    today   = date.today()
    horizon = today + timedelta(days=days)

    qs = AssetItem.objects.filter(
        is_deleted=False,
    ).filter(
        Q(warranty_expiry__lte=horizon) | Q(amc_expiry__lte=horizon)
    ).select_related("asset_type__category").order_by("warranty_expiry", "amc_expiry")

    pks = list(qs.values_list("pk", flat=True))
    active_map = {
        asgn.asset_id: asgn
        for asgn in Assignment.objects.filter(
            asset_id__in=pks, returned_at__isnull=True,
        ).select_related("assignee__employee", "assignee__mp", "assignee__office")
    }

    rows = []
    for asset in qs:
        asgn  = active_map.get(asset.pk)
        holder = asgn.assignee.display_name if asgn else ""
        wty_d  = (asset.warranty_expiry - today).days if asset.warranty_expiry else None
        amc_d  = (asset.amc_expiry      - today).days if asset.amc_expiry      else None
        rd = {
            "asset_tag":      asset.asset_tag,
            "category":       asset.asset_type.category.name,
            "type":           asset.asset_type.name,
            "brand":          asset.brand,
            "model":          asset.model_name,
            "status":         asset.get_status_display(),
            "current_holder": holder,
            "warranty_expiry": _date_str(asset.warranty_expiry),
            "warranty_days":  "" if wty_d is None else wty_d,
            "amc_expiry":     _date_str(asset.amc_expiry),
            "amc_days":       "" if amc_d is None else amc_d,
        }
        rows.append([rd[k] for k in sel_keys])

    data = tabular_pdf(
        title="Warranty / AMC Expiry Report",
        subtitle=f"Assets expiring within {days} days — as of {_date_str(today)}",
        column_labels=labels,
        rows=rows,
        generated_at=timezone.now(),
    )
    return _pdf_response(data, f"warranty_expiry_{date.today():%Y%m%d}.pdf")


@viewer_required
def download_asset_history_pdf(request, pk: int):
    from assets.models import AssetItem
    from assignments.models import Assignment

    asset    = get_object_or_404(AssetItem, pk=pk, is_deleted=False)
    sel_keys = parse_cols(request, ASSET_HISTORY_COLS)
    labels   = [dict(ASSET_HISTORY_COLS)[k] for k in sel_keys]

    history = Assignment.objects.filter(asset=asset).select_related(
        "performed_by", "batch",
    ).order_by("-assigned_at")

    rows = []
    for asgn in history:
        snap = asgn.holder_snapshot or {}
        if asgn.returned_at:
            to_date   = _date_str(asgn.returned_at.date())
            days_held = (asgn.returned_at - asgn.assigned_at).days
        else:
            to_date   = "Current"
            days_held = (timezone.now() - asgn.assigned_at).days
        rd = {
            "assigned_to":  snap.get("display_name", ""),
            "holder_type":  snap.get("assignee_type", ""),
            "designation":  snap.get("designation", ""),
            "department":   snap.get("department", ""),
            "from_date":    _date_str(asgn.assigned_at.date()),
            "to_date":      to_date,
            "days":         days_held,
            "performed_by": asgn.performed_by.get_full_name() or asgn.performed_by.username,
            "batch_ref":    asgn.batch.reference if asgn.batch_id else "",
            "notes":        asgn.notes or "",
        }
        rows.append([rd[k] for k in sel_keys])

    data = tabular_pdf(
        title=f"Asset History — {asset.asset_tag}",
        subtitle=f"{asset.brand} {asset.model_name}  ·  {asset.asset_type.name}",
        column_labels=labels,
        rows=rows,
        generated_at=timezone.now(),
    )
    return _pdf_response(data, f"asset_history_{pk}_{date.today():%Y%m%d}.pdf")


# ── Excel exports ──────────────────────────────────────────────────────────────

@viewer_required
def download_inventory(request):
    spec_keys = ("ram_type", "os_name", "os_licensed")
    filters  = {k: request.GET.get(k) for k in ("status", "category", "type", *spec_keys) if request.GET.get(k)}
    columns  = parse_cols(request, INVENTORY_COLS) if request.GET.get("cols") else None
    filename = f"inventory_{date.today():%Y%m%d}.xlsx"
    return _excel_response(inventory_excel(filters or None, columns), filename)


@viewer_required
def download_transfer_log(request):
    date_from = _parse_date(request.GET.get("date_from"))
    date_to   = _parse_date(request.GET.get("date_to"))
    columns   = parse_cols(request, TRANSFER_LOG_COLS) if request.GET.get("cols") else None
    filename  = f"transfer_log_{date.today():%Y%m%d}.xlsx"
    return _excel_response(transfer_log_excel(date_from, date_to, columns), filename)


@viewer_required
def download_lifecycle(request):
    date_from  = _parse_date(request.GET.get("date_from"))
    date_to    = _parse_date(request.GET.get("date_to"))
    event_type = request.GET.get("event_type") or None
    columns    = parse_cols(request, LIFECYCLE_COLS) if request.GET.get("cols") else None
    filename   = f"lifecycle_events_{date.today():%Y%m%d}.xlsx"
    return _excel_response(lifecycle_events_excel(date_from, date_to, event_type, columns), filename)


@viewer_required
def download_warranty(request):
    try:
        days = int(request.GET.get("days", 90))
        days = max(1, min(days, 3650))
    except (ValueError, TypeError):
        days = 90
    columns  = parse_cols(request, WARRANTY_COLS) if request.GET.get("cols") else None
    filename = f"warranty_expiry_{date.today():%Y%m%d}.xlsx"
    return _excel_response(warranty_expiry_excel(days, columns), filename)


@viewer_required
def download_holder_assignments(request):
    holder_type = request.GET.get("holder_type") or None
    columns     = parse_cols(request, HOLDER_ASSIGNMENTS_COLS) if request.GET.get("cols") else None
    filename    = f"holder_assignments_{date.today():%Y%m%d}.xlsx"
    return _excel_response(holder_assignments_excel(holder_type, columns), filename)


@viewer_required
def download_asset_history(request, pk: int):
    from assets.models import AssetItem
    get_object_or_404(AssetItem, pk=pk, is_deleted=False)
    columns  = parse_cols(request, ASSET_HISTORY_COLS) if request.GET.get("cols") else None
    filename = f"asset_history_{pk}_{date.today():%Y%m%d}.xlsx"
    return _excel_response(asset_history_excel(pk, columns), filename)


# ── PDF exports ────────────────────────────────────────────────────────────────

@viewer_required
def download_handover(request, pk: int):
    from assignments.models import Assignment
    get_object_or_404(Assignment, pk=pk)
    filename = f"handover_{pk}_{date.today():%Y%m%d}.pdf"
    return _pdf_response(handover_pdf(pk), filename)


@viewer_required
def download_disposal(request, pk: int):
    from assets.models import AssetItem
    get_object_or_404(AssetItem, pk=pk)
    filename = f"disposal_certificate_{pk}_{date.today():%Y%m%d}.pdf"
    return _pdf_response(disposal_pdf(pk), filename)
