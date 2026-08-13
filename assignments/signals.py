"""Cache invalidation for the sidebar alert badge."""

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from config.context_processors import ALERT_COUNT_CACHE_KEY

from .models import InactiveHolderAlert


@receiver(post_save, sender=InactiveHolderAlert)
@receiver(post_delete, sender=InactiveHolderAlert)
def clear_open_alert_count(sender, **kwargs):
    """Any raise/resolve/dismiss makes the cached nav badge count stale."""
    cache.delete(ALERT_COUNT_CACHE_KEY)
