from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Upper
from django.utils import timezone

User = get_user_model()


# ---------------------------------------------------------------------------
# Admin-managed catalog lookup tables
# ---------------------------------------------------------------------------

class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Brand"
        verbose_name_plural = "Brands"

    def __str__(self):
        return self.name


class AssetModelName(models.Model):
    name = models.CharField(max_length=200, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Model Name"
        verbose_name_plural = "Model Names"

    def __str__(self):
        return self.name


class Vendor(models.Model):
    name = models.CharField(max_length=200, unique=True)
    contact_info = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Vendor"
        verbose_name_plural = "Vendors"

    def __str__(self):
        return self.name


class SpecChoice(models.Model):
    """Admin-managed dropdown option for a specific spec field key."""
    spec_key = models.CharField(
        max_length=60,
        help_text="e.g. cpu_model, ram_type, storage_type, os_name, gpu_chipset, gpu_memory_type, gpu_capacity",
    )
    value = models.CharField(max_length=200)
    label = models.CharField(max_length=200, blank=True, help_text="Display label; defaults to value if blank")
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["spec_key", "order", "label"]
        unique_together = [("spec_key", "value")]
        verbose_name = "Spec Choice"
        verbose_name_plural = "Spec Choices"

    def __str__(self):
        return f"{self.spec_key}: {self.label or self.value}"

    def display_label(self):
        return self.label or self.value


class WorkOrder(models.Model):
    """Uploaded work order / supply order document (PDF or image)."""
    reference = models.CharField(max_length=100, blank=True)
    document = models.FileField(upload_to="work_orders/")
    description = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="work_orders_uploaded",
    )

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Work Order"
        verbose_name_plural = "Work Orders"

    def __str__(self):
        return self.reference or f"Work Order #{self.pk}"

    @property
    def filename(self):
        import os
        return os.path.basename(self.document.name) if self.document else ""


class AssetCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    name_bn = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Asset Category"
        verbose_name_plural = "Asset Categories"

    def __str__(self) -> str:
        return self.name


class AssetType(models.Model):
    category = models.ForeignKey(
        AssetCategory,
        on_delete=models.PROTECT,
        related_name="asset_types",
    )
    name = models.CharField(max_length=100)
    name_bn = models.CharField(max_length=100, blank=True)
    # True only for PC_SET — enables the AssetComponent inline
    has_components = models.BooleanField(default=False)
    # List of spec field keys relevant to this type, e.g. ["cpu", "ram", "storage"]
    spec_schema = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category__name", "name"]
        verbose_name = "Asset Type"
        verbose_name_plural = "Asset Types"
        unique_together = [("category", "name")]

    def __str__(self) -> str:
        return f"{self.category.name} — {self.name}"


class AssetBatch(models.Model):
    """
    One bulk-add operation. Groups the assets created together on the Bulk Add
    page under a single reference so the batch can be viewed, edited (re-applying
    its shared values to every member asset) and soft-deleted as a unit.

    Holds a snapshot of the *shared* fields entered on the bulk-add form. The
    per-asset fields (serial number, asset tag, status, assignment) are NEVER
    stored here and NEVER changed by a batch edit.
    """

    reference = models.CharField(max_length=50, unique=True)
    asset_type = models.ForeignKey(
        AssetType,
        on_delete=models.PROTECT,
        related_name="batches",
    )
    quantity = models.PositiveIntegerField(default=0)

    # ── Shared snapshot (mirrors the shared bulk-add fields) ────────────────
    brand = models.CharField(max_length=100)
    model_name = models.CharField(max_length=200)
    specifications = models.JSONField(default=dict, blank=True)
    storage_location = models.ForeignKey(
        "locations.Location",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="stored_asset_batches",
    )
    purchase_date = models.DateField(null=True, blank=True)
    purchase_order = models.CharField(max_length=100, blank=True)
    supplier = models.CharField(max_length=200, blank=True)
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)
    amc_expiry = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    work_order = models.ForeignKey(
        WorkOrder,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="batches",
    )

    # Soft delete (architectural convention: never hard-delete)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="asset_batches_created",
    )
    updated_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="asset_batches_updated",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Bulk Add Batch"
        verbose_name_plural = "Bulk Add Batches"
        indexes = [
            models.Index(fields=["is_deleted"]),
        ]

    def __str__(self) -> str:
        return self.reference

    @classmethod
    def generate_reference(cls) -> str:
        """Auto-generate BA-YYYY-NNNN reference (BA = Bulk Add)."""
        year = timezone.now().year
        prefix = f"BA-{year}-"
        last = (
            cls.objects
            .filter(reference__startswith=prefix)
            .order_by("-reference")
            .values_list("reference", flat=True)
            .first()
        )
        seq = int(last.split("-")[-1]) + 1 if last else 1
        return f"{prefix}{seq:04d}"

    @property
    def live_assets(self):
        return self.assets.filter(is_deleted=False)

    def apply_to_assets(self) -> int:
        """
        Push this batch's shared field values onto every live member asset.

        Uses a bulk ``.update()`` so it scales to hundreds of rows. It NEVER
        touches ``status``, ``serial_number``, ``asset_tag`` or assignment —
        assigned/transferred assets keep their state; only the shared values
        change. Returns the number of assets updated.
        """
        return self.assets.filter(is_deleted=False).update(
            asset_type=self.asset_type,
            brand=self.brand,
            model_name=self.model_name,
            specifications=self.specifications,
            storage_location=self.storage_location,
            purchase_date=self.purchase_date,
            purchase_order=self.purchase_order,
            supplier=self.supplier,
            purchase_cost=self.purchase_cost,
            warranty_expiry=self.warranty_expiry,
            amc_expiry=self.amc_expiry,
            notes=self.notes,
            work_order=self.work_order,
            updated_at=timezone.now(),
        )

    def soft_delete(self) -> int:
        """Soft-delete the batch and all its live member assets."""
        now = timezone.now()
        count = self.assets.filter(is_deleted=False).update(
            is_deleted=True, deleted_at=now, updated_at=now,
        )
        self.is_deleted = True
        self.deleted_at = now
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
        return count


# Words typed into the serial field to mean "this unit has no readable serial".
# They are not identities, so they are exempt from the uniqueness rule and may
# repeat as freely as a blank field. Compared upper-cased and stripped.
NON_SERIAL_PLACEHOLDERS: frozenset[str] = frozenset({
    "UNKNOWN", "N/A", "NA", "NIL", "NONE", "NOT SPECIFIED", "NOT AVAILABLE",
    "-", "--", "?", ".",
})


def is_placeholder_serial(value: str) -> bool:
    """True for a blank serial or one of the ``no serial`` placeholder words."""
    cleaned = (value or "").strip()
    return not cleaned or cleaned.upper() in NON_SERIAL_PLACEHOLDERS


def _real_serial_condition() -> models.Q:
    """
    Rows the uniqueness constraint covers: live assets whose serial field holds
    an actual serial — blanks and placeholder words are left out so they can
    repeat.
    """
    condition = models.Q(is_deleted=False) & ~models.Q(serial_number="")
    for placeholder in sorted(NON_SERIAL_PLACEHOLDERS):
        condition &= ~models.Q(serial_number__iexact=placeholder)
    return condition


class AssetItem(models.Model):
    class Status(models.TextChoices):
        IN_STOCK = "IN_STOCK", "In Stock"
        ASSIGNED = "ASSIGNED", "Assigned"
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        LOST = "LOST", "Lost"
        DAMAGED = "DAMAGED", "Damaged"
        DISPOSED = "DISPOSED", "Disposed"

    # Allowed next states for each current status (architectural decision #6)
    VALID_TRANSITIONS: dict[str, set[str]] = {
        Status.IN_STOCK: {Status.ASSIGNED, Status.MAINTENANCE, Status.DISPOSED},
        Status.ASSIGNED: {Status.IN_STOCK, Status.MAINTENANCE, Status.LOST, Status.DAMAGED, Status.DISPOSED},
        Status.MAINTENANCE: {Status.IN_STOCK, Status.DISPOSED},
        Status.LOST: {Status.IN_STOCK, Status.DISPOSED},
        Status.DAMAGED: {Status.IN_STOCK, Status.MAINTENANCE, Status.DISPOSED},
        Status.DISPOSED: set(),  # terminal state
    }

    asset_tag = models.CharField(max_length=50, unique=True)
    asset_type = models.ForeignKey(
        AssetType,
        on_delete=models.PROTECT,
        related_name="items",
    )
    serial_number = models.CharField(max_length=200, blank=True)
    brand = models.CharField(max_length=100)
    model_name = models.CharField(max_length=200)
    specifications = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_STOCK,
    )
    storage_location = models.ForeignKey(
        "locations.Location",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stored_assets",
    )

    # Procurement fields
    purchase_date = models.DateField(null=True, blank=True)
    purchase_order = models.CharField(max_length=100, blank=True)
    supplier = models.CharField(max_length=200, blank=True)
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)
    amc_expiry = models.DateField(null=True, blank=True)

    notes = models.TextField(blank=True)

    # Work order document (shared across bulk-add batches)
    work_order = models.ForeignKey(
        WorkOrder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assets",
    )

    # Bulk-add batch this asset was created in (null for single-add / import)
    batch = models.ForeignKey(
        AssetBatch,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assets",
    )

    # Soft delete (architectural convention: never hard-delete)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assets_created",
    )

    class Meta:
        ordering = ["asset_tag"]
        verbose_name = "Asset"
        verbose_name_plural = "Assets"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["is_deleted"]),
        ]
        constraints = [
            # A serial number identifies one physical unit, so it may appear on
            # at most one live asset. Compared case-insensitively (sn-1 and SN-1
            # are the same plate) and only over rows that still count: blanks
            # and placeholders repeat freely (plenty of old kit has no readable
            # plate) and soft-deleted rows are out of the way so a serial can be
            # re-entered after a mistaken row is deleted.
            models.UniqueConstraint(
                Upper("serial_number"),
                condition=_real_serial_condition(),
                name="uniq_live_asset_serial_ci",
                violation_error_message=(
                    "This serial number is already used by another asset. "
                    "Serial numbers must be unique."
                ),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.asset_tag} — {self.brand} {self.model_name}"

    @classmethod
    def serial_conflict(cls, serial: str, exclude_pk=None) -> "AssetItem | None":
        """
        The live asset already carrying ``serial``, or None if it is free.

        Blank and placeholder serials never conflict. Matching is
        case-insensitive so the same plate typed in a different case is still
        caught.
        """
        serial = (serial or "").strip()
        if is_placeholder_serial(serial):
            return None
        qs = cls.objects.filter(serial_number__iexact=serial, is_deleted=False)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        return qs.first()

    @staticmethod
    def serial_conflict_message(serial: str, other: "AssetItem") -> str:
        """User-facing wording for a duplicate serial — same text everywhere."""
        return (
            f"Serial number '{serial}' is already used by asset {other.asset_tag} "
            f"({other.brand} {other.model_name}). Serial numbers must be unique."
        )

    @property
    def is_assignable(self) -> bool:
        return self.status == self.Status.IN_STOCK and not self.is_deleted

    def change_status(self, new_status: str) -> None:
        """
        Transition to new_status, enforcing the state machine.
        Saves the instance after a valid transition.
        Raises ValidationError on illegal transitions.
        """
        allowed = self.VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValidationError(
                f"Cannot transition from {self.get_status_display()} "
                f"to {AssetItem.Status(new_status).label}."
            )
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

    def clean(self) -> None:
        # Status must be a known value (TextChoices already enforces this at
        # the DB level, but clean() catches it at the form/admin level too).
        if self.status not in self.Status.values:
            raise ValidationError({"status": f"Unknown status: {self.status}"})

        # Duplicate serial: the DB constraint is the real guard, this turns it
        # into a message naming the asset that already holds the serial.
        if not self.is_deleted:
            other = self.serial_conflict(self.serial_number, exclude_pk=self.pk)
            if other is not None:
                raise ValidationError({
                    "serial_number": self.serial_conflict_message(
                        self.serial_number.strip(), other
                    )
                })


class AssetComponent(models.Model):
    class ComponentType(models.TextChoices):
        MONITOR = "MONITOR", "Monitor"
        KEYBOARD = "KEYBOARD", "Keyboard"
        MOUSE = "MOUSE", "Mouse"
        CPU_UNIT = "CPU_UNIT", "CPU Unit"
        RAM = "RAM", "RAM"
        STORAGE_DRIVE = "STORAGE_DRIVE", "Storage Drive"
        SFP = "SFP", "SFP Module"
        NIC = "NIC", "Network Card"
        PSU = "PSU", "Power Supply"
        BATTERY = "BATTERY", "Battery"
        UPS = "UPS", "UPS"
        OTHER = "OTHER", "Other"

    parent_asset = models.ForeignKey(
        AssetItem,
        on_delete=models.PROTECT,
        related_name="components",
    )
    component_type = models.CharField(
        max_length=20,
        choices=ComponentType.choices,
        default=ComponentType.OTHER,
    )
    # Master-data replacement for ``component_type``. The CharField above is
    # kept and backfilled so pre-Phase-13 rows still read correctly; every new
    # row carries both. Referenced by name — catalogue imports this module.
    ctype = models.ForeignKey(
        "catalogue.ComponentType",
        on_delete=models.PROTECT,
        related_name="components",
        null=True,
        blank=True,
    )
    serial_number = models.CharField(max_length=200, blank=True)
    brand = models.CharField(max_length=100, blank=True)
    model_name = models.CharField(max_length=200, blank=True)
    specifications = models.JSONField(default=dict, blank=True)

    # Size of the part in ``unit`` — 16 GB of RAM, 512 GB of storage.
    capacity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=20, blank=True)

    # Procurement — what the part cost, who supplied it, when it was bought.
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="components",
        null=True,
        blank=True,
    )
    purchase_date = models.DateField(null=True, blank=True)
    purchase_order = models.CharField(max_length=100, blank=True)

    # Lifecycle: active=True means currently installed
    is_active = models.BooleanField(default=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    removal_reason = models.CharField(max_length=500, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["parent_asset__asset_tag", "component_type"]
        verbose_name = "Asset Component"
        verbose_name_plural = "Asset Components"

    def __str__(self) -> str:
        return f"{self.label} of {self.parent_asset.asset_tag}"

    @property
    def label(self) -> str:
        """Master-data name where there is one, legacy enum label otherwise."""
        if self.ctype_id is not None:
            return self.ctype.name
        return self.get_component_type_display()

    @property
    def capacity_display(self) -> str:
        """"16 GB" — trailing zeros trimmed so 16.00 does not read as a price."""
        if self.capacity is None:
            return ""
        size = self.capacity.normalize()
        text = format(size, "f") if size == size.to_integral_value() else str(size)
        return f"{text} {self.unit}".strip()

    @property
    def description(self) -> str:
        """One-line summary used in lifecycle notes and the components list."""
        parts = [self.label, self.capacity_display, self.brand, self.model_name]
        return " ".join(p for p in parts if p)

    def clean(self) -> None:
        # Architectural decision #1: components only belong to has_components assets
        if self.parent_asset_id is not None:
            if not self.parent_asset.asset_type.has_components:
                raise ValidationError(
                    {
                        "parent_asset": (
                            f"{self.parent_asset.asset_type.name} does not support "
                            "components. Only PC_SET (or types with has_components=True) "
                            "can have child components."
                        )
                    }
                )

        if self.ctype_id is None:
            return

        ctype = self.ctype
        if self.parent_asset_id is not None and not ctype.available_for(
            self.parent_asset.asset_type
        ):
            raise ValidationError(
                {"ctype": f"{ctype.name} is not offered for {self.parent_asset.asset_type.name}."}
            )

        units = ctype.unit_list
        if self.unit and units and self.unit not in units:
            raise ValidationError(
                {"unit": f"{ctype.name} is measured in {', '.join(units)} — “{self.unit}” is not one of them."}
            )
        if ctype.capacity_required and self.capacity is None:
            raise ValidationError({"capacity": f"{ctype.name} needs a capacity."})
        if self.capacity is not None and self.capacity <= 0:
            raise ValidationError({"capacity": "Capacity must be greater than zero."})
        if self.capacity is not None and units and not self.unit:
            raise ValidationError({"unit": f"Choose a unit for the {ctype.name} capacity."})
        if ctype.serial_required and not self.serial_number.strip():
            raise ValidationError({"serial_number": f"{ctype.name} needs a serial number."})
        if self.cost is not None and self.cost < 0:
            raise ValidationError({"cost": "Cost cannot be negative."})
