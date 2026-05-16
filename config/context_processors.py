from config.permissions import role_context


def role_flags(request):
    if request.user.is_authenticated:
        from assignments.models import InactiveHolderAlert, AlertStatus
        ctx = role_context(request.user)
        ctx["open_alerts_count"] = InactiveHolderAlert.objects.filter(
            status=AlertStatus.OPEN
        ).count()
        return ctx
    return {
        "user_is_admin": False,
        "user_is_it_officer": False,
        "user_is_viewer": False,
        "open_alerts_count": 0,
    }
