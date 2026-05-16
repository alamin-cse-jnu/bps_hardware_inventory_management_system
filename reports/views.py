"""
Parliament IT Inventory — Reports views.

Viewers and above can download all reports. PDF downloads also require
viewer_required since they contain sensitive asset/holder data.
"""

from datetime import date, datetime

from django.shortcuts import get_object_or_404, render

from config.permissions import viewer_required
from reports.generators.excel import (
    asset_history_excel,
    holder_assignments_excel,
    inventory_excel,
    lifecycle_events_excel,
    transfer_log_excel,
    warranty_expiry_excel,
)
from reports.generators.pdf import disposal_pdf, handover_pdf


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


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


@viewer_required
def report_index(request):
    return render(request, "reports/index.html")


# ── Excel exports ─────────────────────────────────────────────────────────────

@viewer_required
def download_inventory(request):
    filters = {
        k: request.GET.get(k)
        for k in ("status", "category", "type")
        if request.GET.get(k)
    }
    filename = f"inventory_{date.today():%Y%m%d}.xlsx"
    return _excel_response(inventory_excel(filters or None), filename)


@viewer_required
def download_transfer_log(request):
    date_from = _parse_date(request.GET.get("date_from"))
    date_to = _parse_date(request.GET.get("date_to"))
    filename = f"transfer_log_{date.today():%Y%m%d}.xlsx"
    return _excel_response(transfer_log_excel(date_from, date_to), filename)


@viewer_required
def download_lifecycle(request):
    date_from = _parse_date(request.GET.get("date_from"))
    date_to = _parse_date(request.GET.get("date_to"))
    event_type = request.GET.get("event_type") or None
    filename = f"lifecycle_events_{date.today():%Y%m%d}.xlsx"
    return _excel_response(
        lifecycle_events_excel(date_from, date_to, event_type), filename
    )


@viewer_required
def download_warranty(request):
    try:
        days = int(request.GET.get("days", 90))
        days = max(1, min(days, 3650))
    except (ValueError, TypeError):
        days = 90
    filename = f"warranty_expiry_{date.today():%Y%m%d}.xlsx"
    return _excel_response(warranty_expiry_excel(days), filename)


@viewer_required
def download_holder_assignments(request):
    holder_type = request.GET.get("holder_type") or None
    filename = f"holder_assignments_{date.today():%Y%m%d}.xlsx"
    return _excel_response(holder_assignments_excel(holder_type), filename)


@viewer_required
def download_asset_history(request, pk: int):
    from assets.models import AssetItem
    get_object_or_404(AssetItem, pk=pk, is_deleted=False)
    filename = f"asset_history_{pk}_{date.today():%Y%m%d}.xlsx"
    return _excel_response(asset_history_excel(pk), filename)


# ── PDF exports ───────────────────────────────────────────────────────────────

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
