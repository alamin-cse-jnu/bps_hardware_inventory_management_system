import io

import qrcode
import qrcode.image.svg
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from assets.models import AssetItem
from assignments.models import Assignment
from config.permissions import it_officer_required, viewer_required
from locations.models import Location

from .models import AuditScan, AuditSession


# ── Audit sessions ────────────────────────────────────────────────────────────

@it_officer_required
def audit_list(request):
    sessions = AuditSession.objects.select_related(
        "performed_by", "location",
    ).prefetch_related("scans")
    return render(request, "qrcodes/audit_list.html", {"sessions": sessions})


@it_officer_required
def audit_create(request):
    if request.method == "POST":
        note = request.POST.get("note", "").strip()
        location_id = request.POST.get("location_id") or None
        location = None
        if location_id:
            location = get_object_or_404(Location, pk=location_id)
        session = AuditSession.objects.create(
            reference=AuditSession.generate_reference(),
            performed_by=request.user,
            location=location,
            note=note,
        )
        messages.success(request, f"Audit session {session.reference} created.")
        return redirect("qrcodes:audit_detail", pk=session.pk)

    locations = Location.objects.order_by("name")
    return render(request, "qrcodes/audit_create.html", {"locations": locations})


@it_officer_required
def audit_detail(request, pk):
    session = get_object_or_404(
        AuditSession.objects.select_related("performed_by", "location")
        .prefetch_related("scans__asset__asset_type", "scans__found_location"),
        pk=pk,
    )
    error = None

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_scan":
            tag = request.POST.get("asset_tag", "").strip().upper()
            note = request.POST.get("note", "").strip()
            found_location_id = request.POST.get("found_location_id") or None

            try:
                asset = AssetItem.objects.get(asset_tag=tag, is_deleted=False)
            except AssetItem.DoesNotExist:
                error = f"Asset tag '{tag}' not found."
            else:
                _, created = AuditScan.objects.get_or_create(
                    session=session, asset=asset,
                    defaults={
                        "note": note,
                        "found_location_id": found_location_id or None,
                    },
                )
                if not created:
                    error = f"{tag} has already been scanned in this session."

        elif action == "complete" and not session.is_complete:
            session.complete()
            messages.success(request, f"Audit session {session.reference} marked complete.")
            return redirect("qrcodes:audit_detail", pk=session.pk)

    locations = Location.objects.order_by("name")
    return render(request, "qrcodes/audit_detail.html", {
        "session": session,
        "locations": locations,
        "error": error,
    })


@it_officer_required
@require_POST
def audit_scan_delete(request, session_pk, scan_pk):
    session = get_object_or_404(AuditSession, pk=session_pk)
    if not session.is_complete:
        AuditScan.objects.filter(pk=scan_pk, session=session).delete()
    return redirect("qrcodes:audit_detail", pk=session_pk)


# ── QR display ────────────────────────────────────────────────────────────────

@viewer_required
def mobile_scan(request, asset_tag):
    asset = get_object_or_404(
        AssetItem.objects.select_related(
            "asset_type__category", "storage_location"
        ),
        asset_tag=asset_tag,
        is_deleted=False,
    )

    active_assignment = (
        Assignment.objects.filter(asset=asset, returned_at__isnull=True)
        .select_related("assignee__employee", "assignee__mp", "assignee__office")
        .first()
    )

    return render(request, "qrcodes/mobile_scan.html", {
        "asset": asset,
        "active_assignment": active_assignment,
    })


@viewer_required
def qr_download(request, pk):
    asset = get_object_or_404(AssetItem, pk=pk, is_deleted=False)
    scan_url = request.build_absolute_uri(
        reverse("qrcodes:mobile_scan", args=[asset.asset_tag])
    )

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(scan_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#006633", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    response = HttpResponse(buf.read(), content_type="image/png")
    response["Content-Disposition"] = f'attachment; filename="QR-{asset.asset_tag}.png"'
    return response


@viewer_required
def qr_label(request, pk):
    asset = get_object_or_404(AssetItem, pk=pk, is_deleted=False)
    scan_url = request.build_absolute_uri(
        reverse("qrcodes:mobile_scan", args=[asset.asset_tag])
    )

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(scan_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#006633", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    import base64
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return render(request, "qrcodes/qr_label.html", {
        "asset": asset,
        "qr_b64": qr_b64,
    })
