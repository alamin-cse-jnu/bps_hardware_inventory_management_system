from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from assets.models import AssetComponent, AssetItem, Vendor
from catalogue.models import ComponentType
from config.permissions import it_officer_required

from .models import EventType
from .services import (
    APPLICABLE_EVENTS, EVENT_HANDLERS,
    add_component, remove_component, swap_component,
)

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


def _resolve_ctype(raw, offered):
    """The posted part must be one this asset actually offers, not just any id."""
    try:
        pk = int(raw)
    except (TypeError, ValueError):
        raise ValidationError("Choose a part.")
    match = next((c for c in offered if c.pk == pk), None)
    if match is None:
        raise ValidationError("That part is not offered for this asset type.")
    return match


def _decimal(raw, label):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        raise ValidationError(f"{label} must be a number.")


def _component_details(request, ctype):
    """
    Pull the capacity / procurement fields off the POST, typed and validated.

    Field-level rules (capacity required, unit within the part's units, cost not
    negative) are left to ``AssetComponent.clean()`` so the panel and any other
    caller cannot drift apart — only parsing happens here.
    """
    unit = request.POST.get("unit", "").strip()
    # A part with exactly one unit needs no chip in the UI; fill it in silently.
    if not unit and len(ctype.unit_list) == 1:
        unit = ctype.unit_list[0]

    vendor_id = (request.POST.get("vendor") or "").strip()
    vendor = None
    if vendor_id:
        vendor = Vendor.objects.filter(pk=vendor_id, is_active=True).first()
        if vendor is None:
            raise ValidationError("Unknown vendor.")

    raw_date = (request.POST.get("purchase_date") or "").strip()
    purchase_date = None
    if raw_date:
        purchase_date = parse_date(raw_date)
        if purchase_date is None:
            raise ValidationError("Purchase date must be YYYY-MM-DD.")
        if purchase_date > timezone.localdate():
            raise ValidationError("Purchase date cannot be in the future.")

    return {
        "capacity": _decimal(request.POST.get("capacity"), "Capacity"),
        "unit": unit,
        "cost": _decimal(request.POST.get("cost"), "Cost"),
        "vendor": vendor,
        "purchase_date": purchase_date,
        "purchase_order": request.POST.get("purchase_order", "").strip(),
    }


@it_officer_required
@require_http_methods(["GET", "POST"])
def component_panel(request, asset_pk):
    """
    Manage the swappable parts of a has_components asset: add, replace, or
    remove components. Each action logs a lifecycle event and leaves the host's
    status and assignment untouched. Re-renders the panel after each action so
    several parts can be handled in one session.
    """
    asset = get_object_or_404(AssetItem, pk=asset_pk, is_deleted=False)
    if not asset.asset_type.has_components:
        return render(request, "lifecycle/component_panel.html", {
            "asset": asset,
            "unsupported": True,
        })

    error = success = None

    # Parts on offer here: active master data explicitly mapped to this asset's
    # Sub Asset. ``applies_to`` is an allow-list — an unmapped part is offered
    # nowhere, so it never reaches this dropdown.
    offered = list(
        ComponentType.objects.filter(is_active=True, applies_to=asset.asset_type)
        .distinct()
        .order_by("order", "name")
    )

    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        note = request.POST.get("note", "").strip()
        try:
            if action in ("add", "replace"):
                ctype = _resolve_ctype(request.POST.get("ctype"), offered)
                details = _component_details(request, ctype)
                brand = request.POST.get("brand", "").strip()
                model = request.POST.get("model_name", "").strip()
                serial = request.POST.get("serial_number", "").strip()

                if action == "add":
                    add_component(
                        asset, "", brand, model, serial, request.user,
                        note=note, ctype=ctype, **details,
                    )
                    success = f"Added {ctype.name}."
                else:
                    old = get_object_or_404(
                        AssetComponent, pk=request.POST.get("old_component_id"),
                        parent_asset=asset, is_active=True,
                    )
                    swap_component(
                        asset, old, "", brand, model, serial, request.user,
                        note=note, ctype=ctype, **details,
                    )
                    success = f"Replaced {old.label}."
            elif action == "remove":
                comp = get_object_or_404(
                    AssetComponent, pk=request.POST.get("component_id"),
                    parent_asset=asset, is_active=True,
                )
                remove_component(asset, comp, request.user, note=note)
                success = f"Removed {comp.label}."
            else:
                error = "Unknown action."
        except ValidationError as exc:
            error = " ".join(exc.messages)

    return render(request, "lifecycle/component_panel.html", {
        "asset": asset,
        "active_components": (
            asset.components.filter(is_active=True)
            .select_related("ctype", "vendor")
            .order_by("component_type")
        ),
        "component_types": offered,
        "vendors": Vendor.objects.filter(is_active=True).order_by("name"),
        "error": error,
        "success": success,
    })
