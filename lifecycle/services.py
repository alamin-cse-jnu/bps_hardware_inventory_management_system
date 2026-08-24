"""
Lifecycle service layer.

Each public function performs one state transition on an AssetItem:
  1. Validates that the current status permits the transition.
  2. Closes any active assignment when the asset leaves ASSIGNED status.
  3. Calls asset.change_status() — which enforces VALID_TRANSITIONS and saves.
  4. Creates and returns a LifecycleEvent audit record.

All functions are wrapped in a single atomic transaction.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from assets.models import AssetComponent, AssetItem

from .models import EventType, LifecycleEvent

User = get_user_model()

# ── internal ──────────────────────────────────────────────────────────────────

def _close_active_assignment(asset: AssetItem) -> None:
    """Close the open assignment (if any) without triggering the immutability guard."""
    from assignments.models import Assignment
    now = timezone.now()
    Assignment.objects.filter(asset=asset, returned_at__isnull=True).update(
        returned_at=now, updated_at=now,
    )


def _make_event(
    asset: AssetItem,
    event_type: str,
    old_status: str,
    new_status: str,
    performed_by: User,
    note: str = "",
    component: AssetComponent | None = None,
) -> LifecycleEvent:
    return LifecycleEvent.objects.create(
        asset=asset,
        event_type=event_type,
        old_status=old_status,
        new_status=new_status,
        performed_by=performed_by,
        note=note,
        component=component,
    )


# ── public API ────────────────────────────────────────────────────────────────

@transaction.atomic
def send_to_maintenance(
    asset: AssetItem, performed_by: User, note: str = "",
) -> LifecycleEvent:
    """IN_STOCK / ASSIGNED / DAMAGED → MAINTENANCE."""
    old_status = asset.status
    if old_status == AssetItem.Status.ASSIGNED:
        _close_active_assignment(asset)
    asset.change_status(AssetItem.Status.MAINTENANCE)
    return _make_event(asset, EventType.MAINTENANCE_SENT, old_status, AssetItem.Status.MAINTENANCE, performed_by, note)


@transaction.atomic
def return_from_maintenance(
    asset: AssetItem, performed_by: User, note: str = "",
) -> LifecycleEvent:
    """MAINTENANCE → IN_STOCK."""
    old_status = asset.status
    asset.change_status(AssetItem.Status.IN_STOCK)
    return _make_event(asset, EventType.MAINTENANCE_RETURN, old_status, AssetItem.Status.IN_STOCK, performed_by, note)


@transaction.atomic
def report_lost(
    asset: AssetItem, performed_by: User, note: str = "",
) -> LifecycleEvent:
    """ASSIGNED → LOST.  Closes the active assignment."""
    old_status = asset.status
    _close_active_assignment(asset)
    asset.change_status(AssetItem.Status.LOST)
    return _make_event(asset, EventType.LOST, old_status, AssetItem.Status.LOST, performed_by, note)


@transaction.atomic
def report_damaged(
    asset: AssetItem, performed_by: User, note: str = "",
) -> LifecycleEvent:
    """ASSIGNED → DAMAGED.  Closes the active assignment."""
    old_status = asset.status
    _close_active_assignment(asset)
    asset.change_status(AssetItem.Status.DAMAGED)
    return _make_event(asset, EventType.DAMAGED, old_status, AssetItem.Status.DAMAGED, performed_by, note)


@transaction.atomic
def recover_asset(
    asset: AssetItem, performed_by: User, note: str = "",
) -> LifecycleEvent:
    """LOST → IN_STOCK."""
    old_status = asset.status
    asset.change_status(AssetItem.Status.IN_STOCK)
    return _make_event(asset, EventType.RECOVERED, old_status, AssetItem.Status.IN_STOCK, performed_by, note)


@transaction.atomic
def repair_asset(
    asset: AssetItem, performed_by: User, note: str = "",
) -> LifecycleEvent:
    """DAMAGED → IN_STOCK."""
    if asset.status != AssetItem.Status.DAMAGED:
        raise ValidationError("Only DAMAGED assets can be repaired.")
    old_status = asset.status
    asset.change_status(AssetItem.Status.IN_STOCK)
    return _make_event(asset, EventType.REPAIRED, old_status, AssetItem.Status.IN_STOCK, performed_by, note)


@transaction.atomic
def dispose_asset(
    asset: AssetItem, performed_by: User, note: str = "",
) -> LifecycleEvent:
    """Any status except DISPOSED → DISPOSED.  Closes any active assignment."""
    old_status = asset.status
    _close_active_assignment(asset)
    asset.change_status(AssetItem.Status.DISPOSED)
    return _make_event(asset, EventType.DISPOSED, old_status, AssetItem.Status.DISPOSED, performed_by, note)


def _legacy_value(code: str) -> str:
    """
    Best-effort mapping of a ComponentType code back onto the legacy enum.

    The ``component_type`` column is still written so pre-Phase-13 rows and new
    ones sort and read the same way (Meta.ordering uses it). A part an Admin
    invented after Phase 13 has no enum member and lands on OTHER — ``ctype`` is
    what actually names it.
    """
    try:
        return AssetComponent.ComponentType((code or "").upper().replace("-", "_")).value
    except ValueError:
        return AssetComponent.ComponentType.OTHER


def _build_component(
    asset: AssetItem,
    component_type: str,
    brand: str,
    model: str,
    serial: str,
    *,
    ctype=None,
    capacity=None,
    unit: str = "",
    cost=None,
    vendor=None,
    purchase_date=None,
    purchase_order: str = "",
) -> AssetComponent:
    """
    Create one component row, validated.

    ``ctype`` is the master-data part (Phase 13); ``component_type`` is the
    legacy enum value, still accepted so existing callers keep working. Passing
    ``ctype`` fills the legacy column from it. ``full_clean`` runs the capacity,
    unit, serial and cost rules defined on the model, so the panel and any
    other caller enforce them identically.
    """
    if ctype is not None:
        component_type = _legacy_value(getattr(ctype, "code", ""))

    comp = AssetComponent(
        parent_asset=asset,
        ctype=ctype,
        component_type=component_type,
        brand=brand,
        model_name=model,
        serial_number=serial,
        capacity=capacity,
        unit=unit,
        cost=cost,
        vendor=vendor,
        purchase_date=purchase_date,
        purchase_order=purchase_order,
        is_active=True,
    )
    comp.full_clean()
    comp.save()
    return comp


@transaction.atomic
def swap_component(
    asset: AssetItem,
    old_component: AssetComponent,
    new_component_type: str,
    new_brand: str,
    new_model: str,
    new_serial: str,
    performed_by: User,
    note: str = "",
    **details,
) -> LifecycleEvent:
    """
    Replace a component on a PC_SET (or any has_components asset).

    Marks the old component inactive and creates a new AssetComponent row.
    Status is unchanged. ``details`` carries the Phase 13 master-data and
    procurement fields — see ``_build_component``.
    """
    if old_component.parent_asset_id != asset.pk:
        raise ValidationError("Component does not belong to this asset.")
    if not asset.asset_type.has_components:
        raise ValidationError(f"{asset.asset_type.name} does not support components.")

    new_comp = _build_component(
        asset, new_component_type, new_brand, new_model, new_serial, **details
    )

    now = timezone.now()
    old_component.is_active = False
    old_component.removed_at = now
    old_component.removal_reason = note or "Replaced during component swap"
    old_component.save(update_fields=["is_active", "removed_at", "removal_reason", "updated_at"])

    return _make_event(
        asset, EventType.COMPONENT_SWAP,
        old_status=asset.status, new_status=asset.status,
        performed_by=performed_by, note=note,
        component=new_comp,
    )


@transaction.atomic
def add_component(
    asset: AssetItem,
    component_type: str,
    brand: str,
    model: str,
    serial: str,
    performed_by: User,
    note: str = "",
    **details,
) -> LifecycleEvent:
    """
    Install a new component on a has_components asset (e.g. an extra RAM stick,
    an SFP module). Status and assignment are unchanged. ``details`` carries the
    Phase 13 master-data and procurement fields — see ``_build_component``.
    """
    if not asset.asset_type.has_components:
        raise ValidationError(f"{asset.asset_type.name} does not support components.")

    new_comp = _build_component(asset, component_type, brand, model, serial, **details)
    return _make_event(
        asset, EventType.COMPONENT_ADD,
        old_status=asset.status, new_status=asset.status,
        performed_by=performed_by, note=note,
        component=new_comp,
    )


@transaction.atomic
def remove_component(
    asset: AssetItem,
    component: AssetComponent,
    performed_by: User,
    note: str = "",
) -> LifecycleEvent:
    """
    Remove (decommission) a component from a has_components asset. The component
    row is kept (is_active=False) with a removal reason + date for the record.
    Status and assignment are unchanged.
    """
    if component.parent_asset_id != asset.pk:
        raise ValidationError("Component does not belong to this asset.")
    if not component.is_active:
        raise ValidationError("Component is already removed.")

    now = timezone.now()
    component.is_active = False
    component.removed_at = now
    component.removal_reason = note or "Removed"
    component.save(update_fields=["is_active", "removed_at", "removal_reason", "updated_at"])

    return _make_event(
        asset, EventType.COMPONENT_REMOVE,
        old_status=asset.status, new_status=asset.status,
        performed_by=performed_by, note=note,
        component=component,
    )


# ── dispatcher (used by the view) ─────────────────────────────────────────────

# Maps EventType value → the service function for that event
EVENT_HANDLERS = {
    EventType.MAINTENANCE_SENT:   send_to_maintenance,
    EventType.MAINTENANCE_RETURN: return_from_maintenance,
    EventType.LOST:               report_lost,
    EventType.DAMAGED:            report_damaged,
    EventType.RECOVERED:          recover_asset,
    EventType.REPAIRED:           repair_asset,
    EventType.DISPOSED:           dispose_asset,
}

# Maps current asset status → list of applicable EventTypes (excluding COMPONENT_SWAP)
APPLICABLE_EVENTS = {
    AssetItem.Status.IN_STOCK: [
        EventType.MAINTENANCE_SENT,
        EventType.DISPOSED,
    ],
    AssetItem.Status.ASSIGNED: [
        EventType.MAINTENANCE_SENT,
        EventType.LOST,
        EventType.DAMAGED,
        EventType.DISPOSED,
    ],
    AssetItem.Status.MAINTENANCE: [
        EventType.MAINTENANCE_RETURN,
        EventType.DISPOSED,
    ],
    AssetItem.Status.LOST: [
        EventType.RECOVERED,
        EventType.DISPOSED,
    ],
    AssetItem.Status.DAMAGED: [
        EventType.REPAIRED,
        EventType.MAINTENANCE_SENT,
        EventType.DISPOSED,
    ],
    AssetItem.Status.DISPOSED: [],
}
