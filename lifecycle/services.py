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
) -> LifecycleEvent:
    """
    Replace a component on a PC_SET (or any has_components asset).

    Marks the old component inactive and creates a new AssetComponent row.
    Status is unchanged.
    """
    if old_component.parent_asset_id != asset.pk:
        raise ValidationError("Component does not belong to this asset.")
    if not asset.asset_type.has_components:
        raise ValidationError(f"{asset.asset_type.name} does not support components.")

    now = timezone.now()
    old_component.is_active = False
    old_component.removed_at = now
    old_component.removal_reason = note or "Replaced during component swap"
    old_component.save(update_fields=["is_active", "removed_at", "removal_reason", "updated_at"])

    new_comp = AssetComponent.objects.create(
        parent_asset=asset,
        component_type=new_component_type,
        brand=new_brand,
        model_name=new_model,
        serial_number=new_serial,
        is_active=True,
    )

    return _make_event(
        asset, EventType.COMPONENT_SWAP,
        old_status=asset.status, new_status=asset.status,
        performed_by=performed_by, note=note,
        component=new_comp,
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
