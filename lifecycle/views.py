from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from assets.models import AssetItem
from config.permissions import it_officer_required

from .models import EventType
from .services import APPLICABLE_EVENTS, EVENT_HANDLERS

_EVENT_LABELS = {
    EventType.MAINTENANCE_SENT:   "Send to Maintenance",
    EventType.MAINTENANCE_RETURN: "Return from Maintenance",
    EventType.LOST:               "Report as Lost",
    EventType.DAMAGED:            "Report as Damaged",
    EventType.RECOVERED:          "Mark as Recovered",
    EventType.REPAIRED:           "Mark as Repaired",
    EventType.DISPOSED:           "Dispose Asset",
}

_EVENT_DESCRIPTIONS = {
    EventType.MAINTENANCE_SENT:   "The asset will be sent for repair/maintenance. Any active assignment will be closed.",
    EventType.MAINTENANCE_RETURN: "The asset has returned from maintenance and will be set to In Stock.",
    EventType.LOST:               "The asset will be flagged as lost. Any active assignment will be closed.",
    EventType.DAMAGED:            "The asset will be flagged as damaged. Any active assignment will be closed.",
    EventType.RECOVERED:          "The lost asset has been found and will be set to In Stock.",
    EventType.REPAIRED:           "The damaged asset has been repaired and will be set to In Stock.",
    EventType.DISPOSED:           "This is irreversible — the asset will be permanently disposed. Any active assignment will be closed.",
}

_EVENT_DANGER = {EventType.DISPOSED, EventType.LOST}


@it_officer_required
@require_http_methods(["GET", "POST"])
def event_panel(request, asset_pk):
    asset = get_object_or_404(AssetItem, pk=asset_pk, is_deleted=False)
    applicable = APPLICABLE_EVENTS.get(asset.status, [])

    if request.method == "POST":
        event_type = request.POST.get("event_type", "").strip()
        note = request.POST.get("note", "").strip()

        if event_type not in applicable:
            return render(request, "lifecycle/event_panel.html", {
                "asset": asset,
                "applicable": applicable,
                "event_labels": _EVENT_LABELS,
                "event_descriptions": _EVENT_DESCRIPTIONS,
                "event_danger": _EVENT_DANGER,
                "error": "Invalid event type for current asset status.",
                "selected_type": event_type,
            })

        handler = EVENT_HANDLERS.get(event_type)
        if handler is None:
            return render(request, "lifecycle/event_panel.html", {
                "asset": asset,
                "applicable": applicable,
                "event_labels": _EVENT_LABELS,
                "event_descriptions": _EVENT_DESCRIPTIONS,
                "event_danger": _EVENT_DANGER,
                "error": "Unknown event type.",
                "selected_type": event_type,
            })

        try:
            event = handler(asset, request.user, note=note)
            asset.refresh_from_db()
            return render(request, "lifecycle/event_success.html", {
                "asset": asset,
                "event": event,
                "event_label": _EVENT_LABELS[event_type],
            })
        except ValidationError as exc:
            error = " ".join(exc.messages)

        return render(request, "lifecycle/event_panel.html", {
            "asset": asset,
            "applicable": applicable,
            "event_labels": _EVENT_LABELS,
            "event_descriptions": _EVENT_DESCRIPTIONS,
            "event_danger": _EVENT_DANGER,
            "error": error,
            "selected_type": event_type,
        })

    selected_type = request.GET.get("type", applicable[0] if applicable else "")
    return render(request, "lifecycle/event_panel.html", {
        "asset": asset,
        "applicable": applicable,
        "event_labels": _EVENT_LABELS,
        "event_descriptions": _EVENT_DESCRIPTIONS,
        "event_danger": _EVENT_DANGER,
        "selected_type": selected_type,
    })
