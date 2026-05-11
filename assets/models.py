from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

User = get_user_model()


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

    def __str__(self) -> str:
        return f"{self.asset_tag} — {self.brand} {self.model_name}"

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


class AssetComponent(models.Model):
    class ComponentType(models.TextChoices):
        MONITOR = "MONITOR", "Monitor"
        KEYBOARD = "KEYBOARD", "Keyboard"
        MOUSE = "MOUSE", "Mouse"
        CPU_UNIT = "CPU_UNIT", "CPU Unit"
        RAM = "RAM", "RAM"
        STORAGE_DRIVE = "STORAGE_DRIVE", "Storage Drive"
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
    serial_number = models.CharField(max_length=200, blank=True)
    brand = models.CharField(max_length=100, blank=True)
    model_name = models.CharField(max_length=200, blank=True)
    specifications = models.JSONField(default=dict, blank=True)

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
        return f"{self.get_component_type_display()} of {self.parent_asset.asset_tag}"

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
