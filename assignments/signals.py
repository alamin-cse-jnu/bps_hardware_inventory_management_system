"""Cache invalidation for the sidebar alert badge."""

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from config.context_processors import (
    ALERT_COUNT_CACHE_KEY,
    OFFICE_CHANGE_COUNT_CACHE_KEY,
)

from .models import InactiveHolderAlert, OfficeChangeAlert


@receiver(post_save, sender=InactiveHolderAlert)
@receiver(post_delete, sender=InactiveHolderAlert)
def clear_open_alert_count(sender, **kwargs):
    """Any raise/resolve/dismiss makes the cached nav badge count stale."""
    cache.delete(ALERT_COUNT_CACHE_KEY)


@receiver(post_save, sender=OfficeChangeAlert)
@receiver(post_delete, sender=OfficeChangeAlert)
def clear_open_office_change_count(sender, **kwargs):
    """Same treatment for the office-change badge."""
    cache.delete(OFFICE_CHANGE_COUNT_CACHE_KEY)
