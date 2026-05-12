"""
Assignment service layer.

All business logic for creating and closing assignments lives here.
The Django admin and future views call these functions — never raw ORM
mutations — so invariants are enforced in one place.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from assets.models import AssetItem
from assignees.models import Assignee

from .models import Assignment, TransferBatch

User = get_user_model()


def perform_transfer(
    asset: AssetItem,
    new_assignee: Assignee,
    performed_by: User,
    *,
    batch: TransferBatch | None = None,
    notes: str = "",
) -> Assignment:
    """
    Assign or transfer an asset to a new assignee.

    Handles two cases:
    - IN_STOCK → ASSIGNED  (initial assignment)
    - ASSIGNED → ASSIGNED  (person-to-person / office transfer)

    Both cases close any open assignment first, then open a new one.
    The asset status is set to ASSIGNED in both cases.

    Raises ValidationError on:
    - asset is deleted
    - asset status is not IN_STOCK or ASSIGNED
    - new_assignee is inactive
    """
    # ── Validate ──────────────────────────────────────────────────────────────
    if asset.is_deleted:
        raise ValidationError(f"Asset {asset.asset_tag} has been deleted.")

    assignable_statuses = {AssetItem.Status.IN_STOCK, AssetItem.Status.ASSIGNED}
    if asset.status not in assignable_statuses:
        raise ValidationError(
            f"Cannot assign asset {asset.asset_tag}: "
            f"status is '{asset.get_status_display()}' "
            f"(must be In Stock or Assigned)."
        )

    if not new_assignee.is_active:
        raise ValidationError(
            f"Assignee '{new_assignee.display_name}' is inactive."
        )

    # ── Build snapshot before touching DB ────────────────────────────────────
    snapshot = new_assignee.build_snapshot()

    with transaction.atomic():
        # Close any currently open assignment for this asset
        active_qs = Assignment.objects.filter(asset=asset, returned_at__isnull=True)
        now = timezone.now()
        # Use update() to bypass the immutability guard in save() — this is
        # the one legitimate path that sets returned_at for the first time.
        active_qs.update(returned_at=now, updated_at=now)

        # Update asset status to ASSIGNED (idempotent if already ASSIGNED)
        if asset.status != AssetItem.Status.ASSIGNED:
            asset.status = AssetItem.Status.ASSIGNED
            asset.save(update_fields=["status", "updated_at"])

        return Assignment.objects.create(
            asset=asset,
            assignee=new_assignee,
            assigned_at=now,
            holder_snapshot=snapshot,
            performed_by=performed_by,
            batch=batch,
            notes=notes,
        )


def return_to_stock(
    asset: AssetItem,
    performed_by: User,
    *,
    notes: str = "",
) -> None:
    """
    Return an ASSIGNED asset to IN_STOCK, closing the open assignment.

    Raises ValidationError if asset is not ASSIGNED.
    """
    if asset.status != AssetItem.Status.ASSIGNED:
        raise ValidationError(
            f"Asset {asset.asset_tag} is not currently assigned "
            f"(status: '{asset.get_status_display()}')."
        )

    now = timezone.now()
    with transaction.atomic():
        Assignment.objects.filter(
            asset=asset, returned_at__isnull=True
        ).update(returned_at=now, updated_at=now)

        asset.status = AssetItem.Status.IN_STOCK
        asset.save(update_fields=["status", "updated_at"])
