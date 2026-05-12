import io

import qrcode
import qrcode.image.svg
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from assets.models import AssetItem
from assignments.models import Assignment
from config.permissions import viewer_required


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
