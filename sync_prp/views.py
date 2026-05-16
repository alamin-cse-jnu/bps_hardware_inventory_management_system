from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from assignees.models import CachedEmployee, CachedMP, CachedOffice
from config.permissions import it_officer_required, viewer_required

from .models import SyncLog


@viewer_required
def sync_dashboard(request):
    logs = SyncLog.objects.select_related("triggered_by").order_by("-started_at")[:50]
    latest = logs[0] if logs else None

    context = {
        "logs": logs,
        "latest": latest,
        "emp_total": CachedEmployee.objects.count(),
        "emp_active": CachedEmployee.objects.filter(is_active=True).count(),
        "mp_total": CachedMP.objects.count(),
        "mp_active": CachedMP.objects.filter(is_active=True).count(),
        "office_total": CachedOffice.objects.count(),
        "office_active": CachedOffice.objects.filter(is_active=True).count(),
    }
    return render(request, "sync_prp/sync_dashboard.html", context)


@it_officer_required
@require_POST
def trigger_sync_view(request):
    from .services import run_entity_sync, run_full_sync

    entity = request.POST.get("entity", "all")
    if entity in ("employees", "mps", "offices"):
        log = run_entity_sync(entity, triggered_by=request.user)
        label = entity.capitalize()
    else:
        log = run_full_sync(triggered_by=request.user)
        label = "Full"

    if log.status == SyncLog.Status.SUCCESS:
        messages.success(
            request,
            f"{label} sync complete — +{log.total_added} added, "
            f"~{log.total_updated} updated, !{log.total_flagged} flagged "
            f"({log.duration_seconds:.1f}s)",
        )
    elif log.status == SyncLog.Status.PARTIAL:
        messages.warning(request, f"{label} sync partially completed: {log.error_message}")
    else:
        messages.error(request, f"{label} sync failed: {log.error_message}")

    return redirect("sync_prp:dashboard")


@viewer_required
def sync_log_detail(request, pk):
    log = get_object_or_404(SyncLog, pk=pk)
    entity_counts = [
        ("Employees", log.employees_added, log.employees_updated, log.employees_flagged),
        ("MPs", log.mps_added, log.mps_updated, log.mps_flagged),
        ("Offices", log.offices_added, log.offices_updated, log.offices_flagged),
    ]
    return render(request, "sync_prp/sync_log_detail.html", {"log": log, "entity_counts": entity_counts})


# ── Legacy JSON API endpoints (kept for backward compat) ─────────────────────

@it_officer_required
@require_POST
def trigger_sync(request):
    from .services import run_full_sync
    log = run_full_sync(triggered_by=request.user)
    return JsonResponse({
        "status": log.status,
        "added": log.total_added,
        "updated": log.total_updated,
        "flagged": log.total_flagged,
        "error": log.error_message,
        "duration_seconds": log.duration_seconds,
    })


@viewer_required
def sync_status(request):
    log = SyncLog.objects.order_by("-started_at").first()
    if not log:
        return JsonResponse({"never_synced": True})
    return JsonResponse({
        "status": log.status,
        "started_at": log.started_at.isoformat(),
        "completed_at": log.completed_at.isoformat() if log.completed_at else None,
        "added": log.total_added,
        "updated": log.total_updated,
        "flagged": log.total_flagged,
        "duration_seconds": log.duration_seconds,
    })
