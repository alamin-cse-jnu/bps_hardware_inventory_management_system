"""
Parliament IT Inventory — Excel report generators (openpyxl).

Each public function returns bytes suitable for an HttpResponse.
All reports include Parliament Blue headers and alternating row shading.
"""

import io
from datetime import date, timedelta

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# ── Brand colours ─────────────────────────────────────────────────────────────
_FILL_HDR  = PatternFill("solid", fgColor="0076A7")   # Parliament Blue
_FILL_ALT  = PatternFill("solid", fgColor="E8F3F8")   # light blue tint
_FONT_HDR  = Font(name="Calibri", bold=True, color="FFFFFF", size=10)
_FONT_TITLE = Font(name="Calibri", bold=True, color="0076A7", size=13)
_FONT_ORG  = Font(name="Calibri", italic=True, color="777777", size=9)
_ALIGN_CTR = Alignment(horizontal="center", vertical="center", wrap_text=False)
_ALIGN_L   = Alignment(horizontal="left",   vertical="center", wrap_text=False)


# ── Private helpers ───────────────────────────────────────────────────────────

def _wb_bytes(wb: Workbook) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _title_block(ws, title: str, subtitle: str = "") -> int:
    """Write organisation + report title, return the row index for the header row."""
    ws["A1"] = "Bangladesh Parliament Secretariat · IT Inventory"
    ws["A1"].font = _FONT_ORG
    ws["A2"] = title
    ws["A2"].font = _FONT_TITLE
    ws.row_dimensions[1].height = 14
    ws.row_dimensions[2].height = 22
    if subtitle:
        ws["A3"] = subtitle
        ws["A3"].font = Font(name="Calibri", italic=True, color="777777", size=9)
        ws.row_dimensions[3].height = 14
        return 5   # blank row 4, header at 5
    return 4       # blank row 3, header at 4


def _header_row(ws, row: int, cols: list[str]) -> None:
    for c, label in enumerate(cols, 1):
        cell = ws.cell(row=row, column=c, value=label)
        cell.fill = _FILL_HDR
        cell.font = _FONT_HDR
        cell.alignment = _ALIGN_CTR
    ws.row_dimensions[row].height = 26
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def _data_row(ws, row: int, values: list, alt: bool = False) -> None:
    fill = _FILL_ALT if alt else None
    for c, val in enumerate(values, 1):
        cell = ws.cell(row=row, column=c, value=val)
        cell.alignment = _ALIGN_L
        if fill:
            cell.fill = fill


def _col_widths(ws, widths: list[int]) -> None:
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _date_s(d) -> str:
    if d is None:
        return ""
    return d.strftime("%d %b %Y") if hasattr(d, "strftime") else str(d)


def _dt_s(dt) -> str:
    if dt is None:
        return ""
    return dt.strftime("%d %b %Y %H:%M") if hasattr(dt, "strftime") else str(dt)


# ── Public report functions ───────────────────────────────────────────────────

def inventory_excel(filters: dict | None = None) -> bytes:
    """
    Current inventory: all non-deleted assets with live holder information.
    Optional filters: status, category (pk), type (pk).
    """
    from assets.models import AssetItem
    from assignments.models import Assignment

    filters = filters or {}
    qs = AssetItem.objects.filter(is_deleted=False).select_related(
        "asset_type__category", "storage_location",
    ).order_by("asset_tag")

    if filters.get("status"):
        qs = qs.filter(status=filters["status"])
    if filters.get("category"):
        qs = qs.filter(asset_type__category_id=filters["category"])
    if filters.get("type"):
        qs = qs.filter(asset_type_id=filters["type"])

    pks = list(qs.values_list("pk", flat=True))
    active_map = {
        a.asset_id: a
        for a in Assignment.objects.filter(
            asset_id__in=pks, returned_at__isnull=True,
        ).select_related("assignee__employee", "assignee__mp", "assignee__office")
    }

    wb = Workbook()
    ws = wb.active
    ws.title = "Inventory"
    hrow = _title_block(ws, "Current IT Asset Inventory", f"Generated: {_date_s(date.today())}")

    cols = [
        "Asset Tag", "Category", "Type", "Brand", "Model", "Serial No.",
        "Status", "Storage Location", "Current Holder", "Holder Type",
        "Assigned Since", "Purchase Date", "Warranty Expiry", "AMC Expiry",
    ]
    _header_row(ws, hrow, cols)
    _col_widths(ws, [14, 14, 16, 14, 22, 16, 12, 24, 28, 12, 14, 14, 16, 14])

    for i, asset in enumerate(qs):
        asgn = active_map.get(asset.pk)
        if asgn:
            holder = asgn.assignee.display_name
            htype  = asgn.assignee.get_assignee_type_display()
            since  = _date_s(asgn.assigned_at.date())
        else:
            holder = htype = since = ""

        _data_row(ws, hrow + 1 + i, [
            asset.asset_tag,
            asset.asset_type.category.name,
            asset.asset_type.name,
            asset.brand,
            asset.model_name,
            asset.serial_number,
            asset.get_status_display(),
            asset.storage_location.full_path if asset.storage_location else "",
            holder, htype, since,
            _date_s(asset.purchase_date),
            _date_s(asset.warranty_expiry),
            _date_s(asset.amc_expiry),
        ], alt=(i % 2 == 1))

    return _wb_bytes(wb)


def transfer_log_excel(date_from=None, date_to=None) -> bytes:
    """All assignment records, optionally filtered by date range."""
    from assignments.models import Assignment

    qs = Assignment.objects.select_related(
        "asset__asset_type__category",
        "assignee__employee", "assignee__mp", "assignee__office",
        "performed_by", "batch",
    ).order_by("-assigned_at")

    if date_from:
        qs = qs.filter(assigned_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(assigned_at__date__lte=date_to)

    qs = qs[:5000]

    subtitle = ""
    if date_from or date_to:
        d1 = _date_s(date_from) if date_from else "Start"
        d2 = _date_s(date_to)   if date_to   else "Today"
        subtitle = f"Period: {d1} – {d2}"

    wb = Workbook()
    ws = wb.active
    ws.title = "Transfer Log"
    hrow = _title_block(ws, "Asset Transfer Log", subtitle)

    cols = [
        "Transfer Date", "Asset Tag", "Category", "Type", "Brand", "Model",
        "Assigned To", "Holder Type", "Designation",
        "Status", "Performed By", "Batch Ref", "Notes",
    ]
    _header_row(ws, hrow, cols)
    _col_widths(ws, [18, 14, 14, 16, 14, 22, 28, 12, 32, 14, 22, 14, 32])

    for i, asgn in enumerate(qs):
        asset = asgn.asset
        snap  = asgn.holder_snapshot or {}
        status = "Active" if asgn.returned_at is None else f"Returned {_date_s(asgn.returned_at.date())}"

        _data_row(ws, hrow + 1 + i, [
            _dt_s(asgn.assigned_at),
            asset.asset_tag,
            asset.asset_type.category.name,
            asset.asset_type.name,
            asset.brand,
            asset.model_name,
            snap.get("display_name", ""),
            snap.get("assignee_type", ""),
            snap.get("designation", ""),
            status,
            asgn.performed_by.get_full_name() or asgn.performed_by.username,
            asgn.batch.reference if asgn.batch_id else "",
            asgn.notes,
        ], alt=(i % 2 == 1))

    return _wb_bytes(wb)


def lifecycle_events_excel(date_from=None, date_to=None, event_type=None) -> bytes:
    """Lifecycle events log, optionally filtered by date and event type."""
    from assets.models import AssetItem
    from lifecycle.models import LifecycleEvent

    qs = LifecycleEvent.objects.select_related(
        "asset__asset_type__category", "performed_by",
    ).order_by("-occurred_at")

    if date_from:
        qs = qs.filter(occurred_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(occurred_at__date__lte=date_to)
    if event_type:
        qs = qs.filter(event_type=event_type)

    qs = qs[:5000]

    wb = Workbook()
    ws = wb.active
    ws.title = "Lifecycle Events"
    hrow = _title_block(ws, "Lifecycle Events Log")

    cols = [
        "Date", "Asset Tag", "Category", "Type", "Brand", "Model",
        "Event", "Old Status", "New Status", "Notes", "Performed By",
    ]
    _header_row(ws, hrow, cols)
    _col_widths(ws, [18, 14, 14, 16, 14, 22, 22, 14, 14, 36, 22])

    for i, ev in enumerate(qs):
        try:
            old_label = AssetItem.Status(ev.old_status).label
        except ValueError:
            old_label = ev.old_status
        try:
            new_label = AssetItem.Status(ev.new_status).label
        except ValueError:
            new_label = ev.new_status

        _data_row(ws, hrow + 1 + i, [
            _dt_s(ev.occurred_at),
            ev.asset.asset_tag,
            ev.asset.asset_type.category.name,
            ev.asset.asset_type.name,
            ev.asset.brand,
            ev.asset.model_name,
            ev.get_event_type_display(),
            old_label, new_label,
            ev.note,
            ev.performed_by.get_full_name() or ev.performed_by.username,
        ], alt=(i % 2 == 1))

    return _wb_bytes(wb)


def warranty_expiry_excel(days: int = 90) -> bytes:
    """Assets with warranty or AMC expiring within `days` days."""
    from assets.models import AssetItem
    from assignments.models import Assignment
    from django.db.models import Q

    today   = date.today()
    horizon = today + timedelta(days=days)

    qs = AssetItem.objects.filter(
        is_deleted=False,
    ).filter(
        Q(warranty_expiry__lte=horizon) | Q(amc_expiry__lte=horizon)
    ).select_related("asset_type__category", "storage_location").order_by(
        "warranty_expiry", "amc_expiry",
    )

    pks = list(qs.values_list("pk", flat=True))
    active_map = {
        a.asset_id: a
        for a in Assignment.objects.filter(
            asset_id__in=pks, returned_at__isnull=True,
        ).select_related("assignee__employee", "assignee__mp", "assignee__office")
    }

    wb = Workbook()
    ws = wb.active
    ws.title = "Warranty AMC Expiry"
    hrow = _title_block(
        ws, "Warranty / AMC Expiry Report",
        f"Assets expiring within {days} days — as of {_date_s(today)}",
    )

    cols = [
        "Asset Tag", "Category", "Type", "Brand", "Model", "Status",
        "Current Holder", "Warranty Expiry", "Days (WTY)",
        "AMC Expiry", "Days (AMC)",
    ]
    _header_row(ws, hrow, cols)
    _col_widths(ws, [14, 14, 16, 14, 22, 12, 28, 16, 10, 16, 10])

    for i, asset in enumerate(qs):
        asgn   = active_map.get(asset.pk)
        holder = asgn.assignee.display_name if asgn else ""
        wty_d  = (asset.warranty_expiry - today).days if asset.warranty_expiry else None
        amc_d  = (asset.amc_expiry      - today).days if asset.amc_expiry      else None

        _data_row(ws, hrow + 1 + i, [
            asset.asset_tag,
            asset.asset_type.category.name,
            asset.asset_type.name,
            asset.brand,
            asset.model_name,
            asset.get_status_display(),
            holder,
            _date_s(asset.warranty_expiry), "" if wty_d is None else wty_d,
            _date_s(asset.amc_expiry),      "" if amc_d is None else amc_d,
        ], alt=(i % 2 == 1))

    return _wb_bytes(wb)


def holder_assignments_excel(holder_type: str | None = None) -> bytes:
    """Current active assignments grouped by holder, optionally filtered by type."""
    from assignments.models import Assignment
    from assignees.models import AssigneeType

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
    wb = Workbook()
    ws = wb.active
    ws.title = "Holder Assignments"
    hrow = _title_block(
        ws, "Current Holder Assignments",
        f"{subtitle}  ·  Generated: {_date_s(date.today())}",
    )

    cols = [
        "Holder", "Holder Type", "Designation", "Department",
        "Asset Tag", "Category", "Asset Type", "Brand", "Model", "Status", "Assigned Since",
    ]
    _header_row(ws, hrow, cols)
    _col_widths(ws, [28, 10, 34, 28, 14, 14, 16, 14, 22, 12, 16])

    for i, asgn in enumerate(qs):
        snap = asgn.holder_snapshot or {}
        _data_row(ws, hrow + 1 + i, [
            asgn.assignee.display_name,
            asgn.assignee.get_assignee_type_display(),
            snap.get("designation", ""),
            snap.get("department", ""),
            asgn.asset.asset_tag,
            asgn.asset.asset_type.category.name,
            asgn.asset.asset_type.name,
            asgn.asset.brand,
            asgn.asset.model_name,
            asgn.asset.get_status_display(),
            _date_s(asgn.assigned_at.date()),
        ], alt=(i % 2 == 1))

    return _wb_bytes(wb)


def asset_history_excel(asset_pk: int) -> bytes:
    """Full assignment history for one asset."""
    from assets.models import AssetItem
    from assignments.models import Assignment

    asset = AssetItem.objects.select_related("asset_type__category").get(pk=asset_pk)
    history = Assignment.objects.filter(asset=asset).select_related(
        "performed_by", "batch",
    ).order_by("-assigned_at")

    wb = Workbook()
    ws = wb.active
    ws.title = "Asset History"
    hrow = _title_block(
        ws, f"Asset History — {asset.asset_tag}",
        f"{asset.brand} {asset.model_name}  ·  {asset.asset_type.name}",
    )

    cols = [
        "#", "Assigned To", "Type", "Designation", "Department",
        "From Date", "To Date", "Days", "Performed By", "Batch Ref", "Notes",
    ]
    _header_row(ws, hrow, cols)
    _col_widths(ws, [4, 28, 10, 34, 26, 16, 16, 8, 22, 12, 34])

    for i, asgn in enumerate(history, 1):
        snap = asgn.holder_snapshot or {}
        if asgn.returned_at:
            to_date = _date_s(asgn.returned_at.date())
            days    = (asgn.returned_at - asgn.assigned_at).days
        else:
            to_date = "Current"
            days    = (timezone.now() - asgn.assigned_at).days

        _data_row(ws, hrow + i, [
            i,
            snap.get("display_name", ""),
            snap.get("assignee_type", ""),
            snap.get("designation", ""),
            snap.get("department", ""),
            _date_s(asgn.assigned_at.date()),
            to_date, days,
            asgn.performed_by.get_full_name() or asgn.performed_by.username,
            asgn.batch.reference if asgn.batch_id else "",
            asgn.notes,
        ], alt=(i % 2 == 0))

    return _wb_bytes(wb)
