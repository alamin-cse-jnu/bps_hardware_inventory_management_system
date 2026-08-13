from django.core.cache import cache

from config.permissions import role_context

# The sidebar badge is re-rendered on every page and on every HTMX partial.
# Counting alerts each time is pure overhead, so the value is cached and the
# InactiveHolderAlert post_save signal drops the key whenever it changes.
ALERT_COUNT_CACHE_KEY = "nav:open_alerts_count"
ALERT_COUNT_TTL = 300

ANONYMOUS_FLAGS = {
    "user_is_admin": False,
    "user_is_it_officer": False,
    "user_is_viewer": False,
    "open_alerts_count": 0,
}


def open_alerts_count() -> int:
    count = cache.get(ALERT_COUNT_CACHE_KEY)
    if count is None:
        from assignments.models import AlertStatus, InactiveHolderAlert

        count = InactiveHolderAlert.objects.filter(status=AlertStatus.OPEN).count()
        cache.set(ALERT_COUNT_CACHE_KEY, count, ALERT_COUNT_TTL)
    return count


def role_flags(request):
    if not request.user.is_authenticated:
        return ANONYMOUS_FLAGS

    ctx = role_context(request.user)
    ctx["open_alerts_count"] = open_alerts_count()
    return ctx
