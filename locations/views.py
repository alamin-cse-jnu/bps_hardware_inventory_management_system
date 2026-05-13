from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from config.permissions import it_officer_required, viewer_required

from .models import Location


@viewer_required
def location_list(request):
    buildings = Location.objects.filter(
        level_type=Location.LevelType.BUILDING
    ).order_by("name")
    tree = []
    for building in buildings:
        floors = Location.objects.filter(parent=building).order_by("name")
        floor_data = []
        for floor in floors:
            rooms = list(Location.objects.filter(parent=floor).order_by("name"))
            floor_data.append({"location": floor, "rooms": rooms})
        tree.append({"location": building, "floors": floor_data})
    return render(request, "locations/location_list.html", {"tree": tree})


@it_officer_required
def location_create(request):
    if request.method == "POST":
        return _save_location(request, None)
    return render(request, "locations/location_form.html", {
        "action": "Add",
        "parents": Location.objects.none(),
        "level_types": Location.LevelType.choices,
    })


@it_officer_required
def location_edit(request, pk):
    location = get_object_or_404(Location, pk=pk)
    if request.method == "POST":
        return _save_location(request, location)
    parents = _parents_for(location.level_type)
    return render(request, "locations/location_form.html", {
        "action": "Edit",
        "location": location,
        "parents": parents,
        "level_types": Location.LevelType.choices,
    })


@it_officer_required
def location_delete(request, pk):
    location = get_object_or_404(Location, pk=pk)
    if request.method == "GET":
        asset_count = location.stored_assets.filter(is_deleted=False).count()
        child_count = location.children.filter(is_active=True).count()
        return render(request, "locations/location_delete_confirm.html", {
            "location": location,
            "asset_count": asset_count,
            "child_count": child_count,
        })
    # POST — deactivate if safe
    asset_count = location.stored_assets.filter(is_deleted=False).count()
    child_count = location.children.filter(is_active=True).count()
    if asset_count or child_count:
        messages.error(request, "Cannot deactivate: move assets or deactivate sub-locations first.")
        return redirect("locations:list")
    location.is_active = False
    location.save(update_fields=["is_active", "updated_at"])
    messages.success(request, f'Location "{location.name}" deactivated.')
    return redirect("locations:list")


@viewer_required
def location_parent_options(request):
    """HTMX endpoint — returns parent <option> elements for the chosen level_type."""
    level_type = request.GET.get("level_type", "")
    selected_pk = request.GET.get("parent", "")
    parents = _parents_for(level_type)
    return render(request, "locations/partials/parent_options.html", {
        "parents": parents,
        "selected_pk": selected_pk,
        "level_type": level_type,
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parents_for(level_type):
    if level_type == Location.LevelType.FLOOR:
        return Location.objects.filter(
            level_type=Location.LevelType.BUILDING, is_active=True
        ).order_by("name")
    if level_type == Location.LevelType.ROOM:
        return Location.objects.filter(
            level_type=Location.LevelType.FLOOR, is_active=True
        ).order_by("name")
    return Location.objects.none()


def _save_location(request, instance):
    data = request.POST
    name = data.get("name", "").strip()
    name_bn = data.get("name_bn", "").strip()
    level_type = data.get("level_type", "")
    parent_id = data.get("parent") or None
    is_active = data.get("is_active") == "on"

    errors = {}
    if not name:
        errors["name"] = "Name is required."
    if not level_type:
        errors["level_type"] = "Level type is required."

    if not errors:
        loc = instance if instance else Location(created_by=request.user)
        loc.name = name
        loc.name_bn = name_bn
        loc.level_type = level_type
        loc.parent_id = parent_id
        if instance:
            loc.is_active = is_active
        try:
            loc.full_clean()
            loc.save()
            verb = "updated" if instance else "created"
            messages.success(request, f'Location "{loc.name}" {verb}.')
            return redirect("locations:list")
        except ValidationError as ve:
            for field, msgs in ve.message_dict.items():
                errors[field] = " ".join(msgs)

    parents = _parents_for(level_type)
    return render(request, "locations/location_form.html", {
        "action": "Edit" if instance else "Add",
        "location": instance,
        "parents": parents,
        "level_types": Location.LevelType.choices,
        "errors": errors,
        "form_data": data,
    })
