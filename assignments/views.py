from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from assets.models import AssetItem
from assignees.models import Assignee

from .models import Assignment
from .services import perform_transfer, return_to_stock


@login_required
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


@login_required
def clear_assignee(request, asset_pk):
    asset = get_object_or_404(AssetItem, pk=asset_pk, is_deleted=False)
    return render(request, "assignments/assignee_field.html", {"asset": asset})


@login_required
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
