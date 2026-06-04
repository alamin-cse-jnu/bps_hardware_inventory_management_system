from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from assets.models import AssetItem
from assignees.models import Assignee
from config.permissions import it_officer_required, viewer_required

from .models import AlertStatus, Assignment, InactiveHolderAlert, TransferBatch
from .services import perform_transfer, return_to_stock


class _BulkAsset:
    """Fake asset stub passed to assignee_field.html when no single asset exists."""
    pk = "bulk"

_BULK_ASSET = _BulkAsset()


@it_officer_required
@require_http_methods(["GET", "POST"])
def assign_panel(request, asset_pk):
    asset = get_object_or_404(AssetItem, pk=asset_pk, is_deleted=False)
    mode = "Transfer" if asset.status == AssetItem.Status.ASSIGNED else "Assign"

    if request.method == "POST":
        assignee_id = request.POST.get("assignee_id", "").strip()
        notes = request.POST.get("notes", "").strip()

        if not assignee_id:
            return render(request, "assignments/assign_panel.html", {
                "asset": asset,
                "mode": mode,
                "error": "Please select an assignee before confirming.",
                "past_holders": _past_holders(asset),
            })

        try:
            assignee = Assignee.objects.get(pk=assignee_id, is_active=True)
            assignment = perform_transfer(asset, assignee, request.user, notes=notes)
            asset.refresh_from_db()
            return render(request, "assignments/assign_success.html", {
                "asset": asset,
                "assignment": assignment,
                "assignee": assignee,
            })
        except Assignee.DoesNotExist:
            error = "Selected assignee not found or is no longer active."
        except ValidationError as exc:
            error = " ".join(exc.messages)

        return render(request, "assignments/assign_panel.html", {
            "asset": asset,
            "mode": mode,
            "error": error,
            "past_holders": _past_holders(asset),
        })

    return render(request, "assignments/assign_panel.html", {
        "asset": asset,
        "mode": mode,
        "past_holders": _past_holders(asset),
    })


@it_officer_required
def clear_assignee(request, asset_pk):
    asset = get_object_or_404(AssetItem, pk=asset_pk, is_deleted=False)
    return render(request, "assignments/assignee_field.html", {"asset": asset})


@it_officer_required
@require_http_methods(["GET", "POST"])
def return_panel(request, asset_pk):
    asset = get_object_or_404(AssetItem, pk=asset_pk, is_deleted=False)

    if request.method == "POST":
        notes = request.POST.get("notes", "").strip()
        try:
            return_to_stock(asset, request.user, notes=notes)
            asset.refresh_from_db()
            return render(request, "assignments/return_success.html", {"asset": asset})
        except ValidationError as exc:
            return render(request, "assignments/return_confirm.html", {
                "asset": asset,
                "error": " ".join(exc.messages),
            })

    return render(request, "assignments/return_confirm.html", {"asset": asset})


# ── Bulk return / transfer ────────────────────────────────────────────────────

@it_officer_required
@require_http_methods(["POST"])
def bulk_return(request):
    from_url = request.POST.get("from_url", "/")
    pks_raw = request.POST.getlist("asset_pks")

    if not pks_raw:
        messages.warning(request, "No assets selected.")
        return redirect(from_url)

    assets = list(
        AssetItem.objects.filter(
            pk__in=pks_raw,
            is_deleted=False,
            status=AssetItem.Status.ASSIGNED,
        ).select_related("asset_type")
    )

    if not assets:
        messages.warning(request, "None of the selected assets are currently assigned.")
        return redirect(from_url)

    if not request.POST.get("confirmed"):
        return render(request, "assignments/bulk_return.html", {
            "assets": assets,
            "pks": [str(a.pk) for a in assets],
            "from_url": from_url,
        })

    notes = request.POST.get("notes", "").strip()
    errors, count = [], 0
    for asset in assets:
        try:
            return_to_stock(asset, request.user, notes=notes)
            count += 1
        except ValidationError as exc:
            errors.append(f"{asset.asset_tag}: {' '.join(exc.messages)}")

    if errors:
        messages.warning(request, f"Returned {count} asset(s). Skipped: {'; '.join(errors)}")
    else:
        messages.success(request, f"{count} asset(s) returned to stock.")
    return redirect(from_url)


@it_officer_required
@require_http_methods(["POST"])
def bulk_transfer(request):
    from_url = request.POST.get("from_url", "/")
    pks_raw = request.POST.getlist("asset_pks")

    if not pks_raw:
        messages.warning(request, "No assets selected.")
        return redirect(from_url)

    assets = list(
        AssetItem.objects.filter(
            pk__in=pks_raw,
            is_deleted=False,
            status=AssetItem.Status.ASSIGNED,
        ).select_related("asset_type")
    )

    if not assets:
        messages.warning(request, "None of the selected assets are available for transfer.")
        return redirect(from_url)

    assignee_id = request.POST.get("assignee_id", "").strip()

    if not assignee_id:
        return render(request, "assignments/bulk_transfer.html", {
            "assets": assets,
            "pks": [str(a.pk) for a in assets],
            "from_url": from_url,
            "asset": _BULK_ASSET,
        })

    notes = request.POST.get("notes", "").strip()
    try:
        assignee = Assignee.objects.get(pk=assignee_id, is_active=True)
    except Assignee.DoesNotExist:
        return render(request, "assignments/bulk_transfer.html", {
            "assets": assets,
            "pks": [str(a.pk) for a in assets],
            "from_url": from_url,
            "asset": _BULK_ASSET,
            "error": "Selected assignee not found or is no longer active.",
        })

    batch = TransferBatch.objects.create(
        reference=TransferBatch.generate_reference(),
        performed_by=request.user,
        note=notes,
    )
    errors, count = [], 0
    for asset in assets:
        try:
            perform_transfer(asset, assignee, request.user, batch=batch, notes=notes)
            count += 1
        except ValidationError as exc:
            errors.append(f"{asset.asset_tag}: {' '.join(exc.messages)}")

    if errors:
        messages.warning(
            request,
            f"Transferred {count} asset(s) to {assignee.display_name}. "
            f"Skipped: {'; '.join(errors)}",
        )
    else:
        messages.success(request, f"{count} asset(s) transferred to {assignee.display_name}.")
    return redirect(from_url)


@it_officer_required
def bulk_clear_assignee(request):
    return render(request, "assignments/assignee_field.html", {"asset": _BULK_ASSET})


# ── Inactive holder alerts ────────────────────────────────────────────────────

@viewer_required
def alerts_list(request):
    status_filter = request.GET.get("status", "OPEN")
    if status_filter not in ("OPEN", "RESOLVED", "DISMISSED", "ALL"):
        status_filter = "OPEN"

    qs = InactiveHolderAlert.objects.select_related(
        "assignee__employee", "assignee__mp", "assignee__office", "resolved_by",
    ).annotate(
        active_asset_count=Count(
            "assignee__assignments",
            filter=Q(assignee__assignments__returned_at__isnull=True),
        )
    )
    if status_filter != "ALL":
        qs = qs.filter(status=status_filter)

    counts = {
        "open": InactiveHolderAlert.objects.filter(status=AlertStatus.OPEN).count(),
        "resolved": InactiveHolderAlert.objects.filter(status=AlertStatus.RESOLVED).count(),
        "dismissed": InactiveHolderAlert.objects.filter(status=AlertStatus.DISMISSED).count(),
    }

    return render(request, "assignments/alerts_list.html", {
        "alerts": qs,
        "status_filter": status_filter,
        "counts": counts,
    })


@it_officer_required
@require_http_methods(["GET", "POST"])
def alert_panel(request, pk):
    alert = get_object_or_404(InactiveHolderAlert, pk=pk)

    active_assignments = (
        Assignment.objects.filter(assignee=alert.assignee, returned_at__isnull=True)
        .select_related("asset__asset_type__category")
    )

    if request.method == "POST":
        action = request.POST.get("action", "")
        note = request.POST.get("note", "").strip()

        if action == "resolve":
            alert.resolve(request.user, note=note)
        elif action == "dismiss":
            alert.dismiss(request.user, note=note)
        else:
            return render(request, "assignments/alert_panel.html", {
                "alert": alert,
                "active_assignments": active_assignments,
                "error": "Unknown action.",
            })

        return render(request, "assignments/alert_done.html", {
            "alert": alert,
            "action": action,
        })

    return render(request, "assignments/alert_panel.html", {
        "alert": alert,
        "active_assignments": active_assignments,
    })


# ── helpers ───────────────────────────────────────────────────────────────────

def _past_holders(asset: AssetItem) -> list[dict]:
    seen: set[int] = set()
    result = []
    qs = (
        Assignment.objects.filter(asset=asset, returned_at__isnull=False)
        .select_related("assignee__employee", "assignee__mp", "assignee__office")
        .order_by("-returned_at")[:20]
    )
    for a in qs:
        if a.assignee_id not in seen and a.assignee.is_active:
            seen.add(a.assignee_id)
            result.append({"assignee": a.assignee, "returned_at": a.returned_at})
        if len(result) == 4:
            break
    return result
