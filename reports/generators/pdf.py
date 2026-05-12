"""
Parliament IT Inventory — PDF report generators (WeasyPrint).

Each public function returns bytes suitable for an HttpResponse
with content_type='application/pdf'.
"""

import base64
from datetime import date
from functools import lru_cache

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

try:
    from weasyprint import HTML
    _WEASYPRINT_AVAILABLE = True
except Exception:
    _WEASYPRINT_AVAILABLE = False


@lru_cache(maxsize=1)
def _logo_data_url() -> str:
    """Load parliament logo as base64 data URL (cached after first call)."""
    try:
        logo_path = settings.STATICFILES_DIRS[0] / "images" / "parliament_logo.png"
        with open(logo_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{encoded}"
    except Exception:
        return ""


def _render_pdf(template_name: str, context: dict) -> bytes:
    if not _WEASYPRINT_AVAILABLE:
        raise ImportError("WeasyPrint is not installed or failed to import.")
    context.setdefault("logo_data_url", _logo_data_url())
    html_string = render_to_string(template_name, context)
    return HTML(string=html_string, base_url="").write_pdf()


def handover_pdf(assignment_pk: int) -> bytes:
    """
    Single-asset handover form: asset info, holder, signature block.
    Designed to be printed and signed by the receiving officer.
    """
    from assignments.models import Assignment

    asgn = Assignment.objects.select_related(
        "asset__asset_type__category",
        "asset__storage_location",
        "performed_by",
        "batch",
    ).get(pk=assignment_pk)

    snap = asgn.holder_snapshot or {}
    context = {
        "assignment": asgn,
        "asset": asgn.asset,
        "snap": snap,
        "generated_at": timezone.now(),
        "today": date.today(),
    }
    return _render_pdf("reports/pdf/handover.html", context)


def disposal_pdf(asset_pk: int) -> bytes:
    """
    Disposal certificate for a disposed asset.
    Pulls the most recent DISPOSED lifecycle event for the asset.
    """
    from assets.models import AssetItem
    from lifecycle.models import EventType, LifecycleEvent

    asset = AssetItem.objects.select_related(
        "asset_type__category",
        "storage_location",
    ).get(pk=asset_pk)

    event = (
        LifecycleEvent.objects
        .filter(asset=asset, event_type=EventType.DISPOSED)
        .select_related("performed_by")
        .order_by("-occurred_at")
        .first()
    )

    context = {
        "asset": asset,
        "event": event,
        "generated_at": timezone.now(),
        "today": date.today(),
    }
    return _render_pdf("reports/pdf/disposal.html", context)
