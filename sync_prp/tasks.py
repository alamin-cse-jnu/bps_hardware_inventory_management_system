import datetime

from celery import shared_task
from django.db.models import Q
from django.utils import timezone


@shared_task(name="sync_prp.scheduled_sync")
def scheduled_sync():
    """Daily PRP API sync — runs at 1 AM via Celery Beat."""
    from .services import run_full_sync
    log = run_full_sync(triggered_by=None)
    return {
        "log_id": log.pk,
        "status": log.status,
        "added": log.total_added,
        "updated": log.total_updated,
        "flagged": log.total_flagged,
    }


@shared_task(name="sync_prp.check_expiry")
def check_expiry():
    """
    Daily check for assets with warranty or AMC expiring within 30 days.
    Returns count for monitoring; future work can create alert records here.
    """
    from assets.models import AssetItem

    horizon = timezone.now().date() + datetime.timedelta(days=30)
    today = timezone.now().date()

    count = AssetItem.objects.filter(is_deleted=False).filter(
        Q(warranty_expiry__gt=today, warranty_expiry__lte=horizon) |
        Q(amc_expiry__gt=today, amc_expiry__lte=horizon)
    ).count()

    return {"expiring_within_30_days": count, "checked_at": timezone.now().isoformat()}
