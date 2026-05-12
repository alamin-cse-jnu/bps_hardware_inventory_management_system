from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from assignments.models import Assignment

from .models import AssetItem, AssetType


@login_required
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
        "asset_types": AssetType.objects.filter(is_active=True).select_related("category"),
        "current_status": status,
        "current_type": type_id,
        "q": q,
    })


@login_required
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
