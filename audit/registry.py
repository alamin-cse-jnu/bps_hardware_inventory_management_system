"""
Which models are auto-audited, and which of their fields are diffed.

Each entry maps a ``"app_label.ModelName"`` to a set of field names to *exclude*
from diffing (on top of the global excludes). Status / soft-delete / ownership
changes on assets are captured by dedicated handlers (lifecycle & assignment
signals), so those fields are excluded here to avoid duplicate noise.
"""

# Never diff these on any model.
EXCLUDE_GLOBAL = {"id", "created_at", "updated_at", "password", "last_login"}

TRACKED: dict[str, set[str]] = {
    "assets.AssetCategory":  set(),
    "assets.AssetType":      set(),
    "assets.AssetItem":      {"status", "is_deleted", "deleted_at", "created_by"},
    "assets.AssetComponent": {"is_active", "removed_at"},
    "locations.Location":    set(),
}

# Friendly names for the activity-log model filter / display.
MODEL_LABELS: dict[str, str] = {
    "assets.AssetItem":      "Asset",
    "assets.AssetType":      "Asset Type",
    "assets.AssetCategory":  "Category",
    "assets.AssetComponent": "Component",
    "locations.Location":    "Location",
    "auth.User":             "User",
}


def model_label(model) -> str:
    return f"{model._meta.app_label}.{model.__name__}"


def tracked_fields(model) -> list:
    """Concrete, non-PK fields of ``model`` that should be diffed."""
    exclude = TRACKED.get(model_label(model))
    if exclude is None:
        return []
    fields = []
    for f in model._meta.concrete_fields:
        if f.primary_key or f.name in EXCLUDE_GLOBAL or f.name in exclude:
            continue
        fields.append(f)
    return fields


def pretty_model(target_model: str) -> str:
    return MODEL_LABELS.get(target_model, target_model.split(".")[-1])
