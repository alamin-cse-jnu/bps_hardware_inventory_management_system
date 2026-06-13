"""Audit recording + display helpers."""

import json

from django.contrib.auth.models import AnonymousUser

from .middleware import get_current_user
from .models import AuditLog

_SENTINEL = object()

# Human labels for fields that don't title-case cleanly.
FIELD_LABELS = {
    "name_bn":          "Name (Bangla)",
    "name_en":          "Name",
    "model_name":       "Model",
    "asset_type":       "Type",
    "serial_number":    "Serial No.",
    "storage_location": "Storage Location",
    "amc_expiry":       "AMC Expiry",
    "warranty_expiry":  "Warranty Expiry",
    "purchase_order":   "Purchase Order",
    "purchase_cost":    "Purchase Cost",
    "purchase_date":    "Purchase Date",
    "specifications":   "Specifications",
    "has_components":   "Component Set",
    "is_active":        "Active",
    "spec_schema":      "Spec Fields",
}


def _actor_label(actor) -> str:
    if actor is None or isinstance(actor, AnonymousUser) or not getattr(actor, "is_authenticated", False):
        return "System"
    return actor.get_full_name() or actor.username


def _target_label(instance) -> str:
    for attr in ("asset_tag", "reference", "code", "name", "username"):
        val = getattr(instance, attr, None)
        if val:
            return str(val)[:255]
    return str(instance)[:255]


def record(action, instance, *, actor=_SENTINEL, changes=None, note="") -> AuditLog | None:
    """Write one audit entry. Actor defaults to the current request user."""
    if actor is _SENTINEL:
        actor = get_current_user()
    if actor is not None and (isinstance(actor, AnonymousUser) or not getattr(actor, "is_authenticated", False)):
        actor = None

    return AuditLog.objects.create(
        actor=actor,
        actor_label=_actor_label(actor),
        action=action,
        target_model=f"{instance._meta.app_label}.{instance.__class__.__name__}",
        target_id=str(instance.pk) if instance.pk else "",
        target_label=_target_label(instance),
        changes=changes or {},
        note=note or "",
    )


# ── Display helpers (used by the activity-log page and per-asset timeline) ──────

def humanize_field(name: str) -> str:
    return FIELD_LABELS.get(name, name.replace("_", " ").title())


def humanize_value(v) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, (dict, list)):
        s = json.dumps(v, ensure_ascii=False, default=str)
    else:
        s = str(v)
    return (s[:120] + "…") if len(s) > 120 else s


def format_changes(changes: dict) -> list[dict]:
    """Turn stored {field: [before, after]} into display rows."""
    rows = []
    for field, pair in (changes or {}).items():
        before = pair[0] if isinstance(pair, (list, tuple)) and len(pair) > 0 else None
        after  = pair[1] if isinstance(pair, (list, tuple)) and len(pair) > 1 else None
        rows.append({
            "field":  humanize_field(field),
            "before": humanize_value(before),
            "after":  humanize_value(after),
        })
    return rows


def prepare_entries(entries) -> list[dict]:
    """Wrap AuditLog rows with formatted change details for templates."""
    return [{"log": e, "changes": format_changes(e.changes or {})} for e in entries]
