"""Audit trail views — global Activity Log (Admin only)."""

from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from config.permissions import admin_required

from .models import AuditLog
from .registry import MODEL_LABELS
from .services import prepare_entries

User = get_user_model()


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


@admin_required
def activity_log(request):
    action = request.GET.get("action", "").strip()
    model  = request.GET.get("model", "").strip()
    actor  = request.GET.get("actor", "").strip()
    q      = request.GET.get("q", "").strip()
    date_from = _parse_date(request.GET.get("date_from"))
    date_to   = _parse_date(request.GET.get("date_to"))

    qs = AuditLog.objects.select_related("actor").all()

    if action:
        qs = qs.filter(action=action)
    if model:
        qs = qs.filter(target_model=model)
    if actor:
        if actor == "system":
            qs = qs.filter(actor__isnull=True)
        elif actor.isdigit():
            qs = qs.filter(actor_id=actor)
    if q:
        qs = qs.filter(Q(target_label__icontains=q) | Q(note__icontains=q))
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    try:
        per_page = int(request.GET.get("per_page", 50))
        per_page = per_page if per_page in (25, 50, 100) else 50
    except (ValueError, TypeError):
        per_page = 50

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    rows = prepare_entries(page_obj.object_list)

    # Filter dropdown data
    actors = (
        User.objects.filter(audit_entries__isnull=False)
        .distinct().order_by("username")
    )
    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "audit/activity_log.html", {
        "rows":          rows,
        "page_obj":      page_obj,
        "total_count":   paginator.count,
        "start_index":   page_obj.start_index() if paginator.count else 0,
        "per_page":      per_page,
        "action":        action,
        "model":         model,
        "actor":         actor,
        "q":             q,
        "date_from":     request.GET.get("date_from", ""),
        "date_to":       request.GET.get("date_to", ""),
        "action_choices": AuditLog.Action.choices,
        "model_choices":  sorted(MODEL_LABELS.items(), key=lambda kv: kv[1]),
        "actors":        actors,
        "base_qs":       params.urlencode(),
    })
