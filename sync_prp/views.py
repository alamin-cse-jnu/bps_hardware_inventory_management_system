from django.http import JsonResponse
from django.views.decorators.http import require_POST

from config.permissions import it_officer_required, viewer_required

from .models import SyncLog


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
