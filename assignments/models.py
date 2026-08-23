from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# TransferBatch
# ─────────────────────────────────────────────────────────────────────────────

class TransferBatch(models.Model):
    """
    Groups multiple Assignment transitions under one reference.
    Each asset in the batch can go to a different destination
    (architectural decision #5).
    """

    reference = models.CharField(max_length=50, unique=True)
    note = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="transfer_batches",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Transfer Batch"
        verbose_name_plural = "Transfer Batches"

    def __str__(self) -> str:
        return self.reference

    @classmethod
    def generate_reference(cls) -> str:
        """Auto-generate TB-YYYY-NNNN reference."""
        from django.utils import timezone as tz
        year = tz.now().year
        prefix = f"TB-{year}-"
        last = (
            cls.objects
            .filter(reference__startswith=prefix)
            .order_by("-reference")
            .values_list("reference", flat=True)
            .first()
        )
        if last:
            seq = int(last.split("-")[-1]) + 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"


# ─────────────────────────────────────────────────────────────────────────────
# Assignment
# ─────────────────────────────────────────────────────────────────────────────

class Assignment(models.Model):
    """
    Immutable record linking an asset to an assignee.

    Architectural decisions enforced here:
    - #3: Once returned_at is set the row is NEVER modified again.
    - #4: holder_snapshot freezes name/designation/department at assignment time.

    Creating a transfer: close this row (returned_at = now), open a new one.
    """

    asset = models.ForeignKey(
        "assets.AssetItem",
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    assignee = models.ForeignKey(
        "assignees.Assignee",
        on_delete=models.PROTECT,
        related_name="assignments",
    )

    assigned_at = models.DateTimeField(default=timezone.now)
    returned_at = models.DateTimeField(null=True, blank=True)

    # Frozen holder details at the moment of assignment (architectural decision #4)
    holder_snapshot = models.JSONField()

    performed_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="assignments_performed",
    )
    batch = models.ForeignKey(
        TransferBatch, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="assignments",
    )
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-assigned_at"]
        verbose_name = "Assignment"
        verbose_name_plural = "Assignments"
        indexes = [
            # Fast lookup: all assignments for an asset + find the active one
            models.Index(fields=["asset", "returned_at"]),
            # Fast lookup: all assignments for an assignee + find active ones
            models.Index(fields=["assignee", "returned_at"]),
        ]

    def __str__(self) -> str:
        status = "active" if self.returned_at is None else f"returned {self.returned_at:%Y-%m-%d}"
        return f"{self.asset_id} → {self.assignee_id} ({status})"

    @property
    def is_active(self) -> bool:
        return self.returned_at is None

    def save(self, *args, **kwargs) -> None:
        # Immutability guard (architectural decision #3):
        # Once returned_at is set in the DB, the row is frozen.
        if self.pk is not None:
            existing_returned_at = (
                Assignment.objects
                .filter(pk=self.pk)
                .values_list("returned_at", flat=True)
                .first()
            )
            if existing_returned_at is not None:
                raise ValidationError(
                    f"Assignment {self.pk} is closed (returned_at is set) and cannot be modified."
                )
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# InactiveHolderAlert
# ─────────────────────────────────────────────────────────────────────────────

class AlertStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    RESOLVED = "RESOLVED", "Resolved"
    DISMISSED = "DISMISSED", "Dismissed"


class InactiveHolderAlert(models.Model):
    """
    Raised when a holder disappears from the PRP API while still having
    active assignments. Human remediation required — no automatic returns
    (architectural decision #9).
    """

    assignee = models.ForeignKey(
        "assignees.Assignee",
        on_delete=models.PROTECT,
        related_name="inactive_alerts",
    )
    raised_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=AlertStatus.choices, default=AlertStatus.OPEN,
    )
    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="alerts_resolved",
    )

    class Meta:
        ordering = ["-raised_at"]
        verbose_name = "Inactive Holder Alert"
        verbose_name_plural = "Inactive Holder Alerts"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["assignee", "status"]),
        ]

    def __str__(self) -> str:
        return f"Alert: {self.assignee} [{self.status}]"

    def resolve(self, user: User, note: str = "") -> None:
        self.status = AlertStatus.RESOLVED
        self.resolved_at = timezone.now()
        self.resolved_by = user
        if note:
            self.note = note
        self.save(update_fields=["status", "resolved_at", "resolved_by", "note", "updated_at"])

    def dismiss(self, user: User, note: str = "") -> None:
        self.status = AlertStatus.DISMISSED
        self.resolved_at = timezone.now()
        self.resolved_by = user
        if note:
            self.note = note
        self.save(update_fields=["status", "resolved_at", "resolved_by", "note", "updated_at"])


# ─────────────────────────────────────────────────────────────────────────────
# OfficeChangeAlert
# ─────────────────────────────────────────────────────────────────────────────

# Placement identity — a change in any of these means the holder moved office.
PLACEMENT_ID_FIELDS = ("wing_id", "branch_id", "section_id", "unit_id", "office_id")
# Stored alongside the ids so the alert still reads correctly years later,
# even if the office is renamed or removed from the API.
PLACEMENT_NAME_FIELDS = (
    "wing_name_en", "branch_name_en", "section_name_en", "unit_name_en", "office_name_en",
)


def placement_of(employee) -> dict:
    """Snapshot the office placement of a CachedEmployee as a plain dict."""
    return {
        f: getattr(employee, f, "") or ""
        for f in PLACEMENT_ID_FIELDS + PLACEMENT_NAME_FIELDS
    }


def placement_ids(placement: dict) -> tuple:
    """The comparable part of a placement dict — ids only, names ignored."""
    return tuple((placement or {}).get(f, "") or "" for f in PLACEMENT_ID_FIELDS)


def placement_path(placement: dict) -> str:
    """Human-readable 'Section, Branch, Wing' path for a placement dict."""
    placement = placement or {}
    parts = [
        placement.get("unit_name_en"),
        placement.get("section_name_en"),
        placement.get("branch_name_en"),
        placement.get("wing_name_en"),
    ]
    return ", ".join(p for p in parts if p) or "—"


class OfficeChangeAlert(models.Model):
    """
    Raised when a PRP-sourced employee's office placement changes while they
    still hold assets. Like InactiveHolderAlert, this is a flag only — assets
    are never moved automatically (architectural decision #9). A human decides
    whether the assets follow the holder, return to stock, or stay put.
    """

    assignee = models.ForeignKey(
        "assignees.Assignee",
        on_delete=models.PROTECT,
        related_name="office_change_alerts",
    )
    # Placement before and after the move, frozen at detection time.
    old_placement = models.JSONField(default=dict, blank=True)
    new_placement = models.JSONField(default=dict, blank=True)

    # Not auto_now_add: a second move while the alert is still open refreshes it.
    detected_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=AlertStatus.choices, default=AlertStatus.OPEN,
    )
    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="office_change_alerts_resolved",
    )

    class Meta:
        ordering = ["-detected_at"]
        verbose_name = "Office Change Alert"
        verbose_name_plural = "Office Change Alerts"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["assignee", "status"]),
        ]

    def __str__(self) -> str:
        return f"Office change: {self.assignee} [{self.status}]"

    @property
    def old_path(self) -> str:
        return placement_path(self.old_placement)

    @property
    def new_path(self) -> str:
        return placement_path(self.new_placement)

    def resolve(self, user: User, note: str = "") -> None:
        self.status = AlertStatus.RESOLVED
        self.resolved_at = timezone.now()
        self.resolved_by = user
        if note:
            self.note = note
        self.save(update_fields=["status", "resolved_at", "resolved_by", "note", "updated_at"])

    def dismiss(self, user: User, note: str = "") -> None:
        self.status = AlertStatus.DISMISSED
        self.resolved_at = timezone.now()
        self.resolved_by = user
        if note:
            self.note = note
        self.save(update_fields=["status", "resolved_at", "resolved_by", "note", "updated_at"])
