from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from config.permissions import it_officer_required, viewer_required

from .models import Block, Building, Level, Location


@viewer_required
def location_list(request):
    q = request.GET.get("q", "").strip()
    building_id = request.GET.get("building", "")
    block_id = request.GET.get("block", "")
    level_id = request.GET.get("level", "")

    locations = (
        Location.objects.select_related("building", "block", "level")
        .annotate(asset_count=Count("stored_assets", filter=Q(stored_assets__is_deleted=False)))
        .order_by("name")
    )
    if q:
        locations = locations.filter(
            Q(name__icontains=q)
            | Q(room__icontains=q)
            | Q(building__name__icontains=q)
            | Q(block__name__icontains=q)
            | Q(level__name__icontains=q)
        )
    if building_id:
        locations = locations.filter(building_id=building_id)
    if block_id:
        locations = locations.filter(block_id=block_id)
    if level_id:
        locations = locations.filter(level_id=level_id)

    return render(request, "locations/location_list.html", {
        "locations": locations,
        "buildings": Building.objects.filter(is_active=True).order_by("name"),
        "blocks": Block.objects.filter(is_active=True).order_by("name"),
        "levels": Level.objects.filter(is_active=True).order_by("name"),
        "q": q,
        "sel_building": building_id,
        "sel_block": block_id,
        "sel_level": level_id,
    })


@viewer_required
def location_detail(request, pk):
    from assignments.models import Assignment
    location = get_object_or_404(Location, pk=pk)
    active_assignments = (
        Assignment.objects.filter(assignee__location=location, returned_at__isnull=True)
        .select_related("asset__asset_type__category", "performed_by")
        .order_by("assigned_at")
    )
    return render(request, "locations/location_detail.html", {
        "location": location,
        "active_assignments": active_assignments,
    })


@it_officer_required
def location_create(request):
    if request.method == "POST":
        return _save_location(request, None)
    return render(request, "locations/location_form.html", _form_context("Add"))


@it_officer_required
def location_edit(request, pk):
    location = get_object_or_404(Location, pk=pk)
    if request.method == "POST":
        return _save_location(request, location)
    return render(request, "locations/location_form.html", _form_context("Edit", location=location))


@it_officer_required
def location_delete(request, pk):
    location = get_object_or_404(Location, pk=pk)
    asset_count = location.stored_assets.filter(is_deleted=False).count()
    if request.method == "GET":
        return render(request, "locations/location_delete_confirm.html", {
            "location": location,
            "asset_count": asset_count,
        })
    # POST — deactivate if safe
    if asset_count:
        messages.error(request, "Cannot deactivate: move the stored assets first.")
        return redirect("locations:list")
    location.is_active = False
    location.save(update_fields=["is_active", "updated_at"])
    # Without this the Assignee row stays active and the deactivated location
    # keeps showing up in the assign panel.
    location.sync_assignee()
    messages.success(request, f'Location "{location.name}" deactivated.')
    return redirect("locations:list")


@viewer_required
def location_history_print(request, pk):
    from assignments.models import Assignment
    from assets.models import AssetItem
    from django.utils import timezone
    location = get_object_or_404(Location, pk=pk)
    current_assets = list(
        AssetItem.objects.filter(storage_location=location, is_deleted=False)
        .select_related("asset_type")
        .order_by("asset_tag")
    )
    history = list(
        Assignment.objects.filter(assignee__location=location)
        .select_related("asset", "asset__asset_type", "performed_by")
        .order_by("-assigned_at")
    )
    return render(request, "print/history_print.html", {
        "page_title": f"Location History — {location.name}",
        "location": location,
        "current_assets": current_assets,
        "history": history,
        "generated_at": timezone.now(),
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _form_context(action, *, location=None, errors=None, form_data=None):
    return {
        "action": action,
        "location": location,
        "buildings": Building.objects.filter(is_active=True).order_by("name"),
        "blocks": Block.objects.filter(is_active=True).order_by("name"),
        "levels": Level.objects.filter(is_active=True).order_by("name"),
        "errors": errors or {},
        "form_data": form_data,
    }


def _save_location(request, instance):
    data = request.POST
    name = data.get("name", "").strip()
    room = data.get("room", "").strip()
    building_id = data.get("building") or None
    block_id = data.get("block") or None
    level_id = data.get("level") or None
    is_active = data.get("is_active") == "on"

    errors = {}
    if not name:
        errors["name"] = "Name is required."
    if not (building_id or block_id or level_id):
        errors["dimension"] = "Select at least one of Building, Block or Level."

    if not errors:
        loc = instance if instance else Location(created_by=request.user)
        loc.name = name
        loc.room = room
        loc.building_id = building_id
        loc.block_id = block_id
        loc.level_id = level_id
        if instance:
            loc.is_active = is_active
        try:
            loc.full_clean()
            loc.save()
            # Creates the Assignee row on add, and keeps its is_active in step
            # with the edit form's checkbox on update.
            loc.sync_assignee()
            verb = "updated" if instance else "created"
            messages.success(request, f'Location "{loc.name}" {verb}.')
            return redirect("locations:list")
        except ValidationError as ve:
            for field, msgs in ve.message_dict.items():
                key = field if field != "__all__" else "dimension"
                errors[key] = " ".join(msgs)

    return render(
        request, "locations/location_form.html",
        _form_context("Edit" if instance else "Add", location=instance, errors=errors, form_data=data),
    )
