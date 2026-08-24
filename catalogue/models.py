"""
Centrally-managed master data for the cascading asset catalogue.

The 4-level hierarchy reuses the existing catalog for its top two levels:

    Main Asset  = assets.AssetCategory   (Level 1)
    Sub Asset   = assets.AssetType       (Level 2)
    Brand       = catalogue.CatalogBrand (Level 3, scoped to a Sub Asset)
    Model       = catalogue.CatalogModel (Level 4, scoped to a Brand)

Each Sub Asset also owns an ordered set of ``SubAssetSpecField`` definitions —
the master-data-driven specification schema. The asset entry form renders a
matching widget for every field, so the dropdown values, units, and toggles are
all controlled here rather than hardcoded in templates.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from assets.models import AssetType


class CatalogBrand(models.Model):
    """Level 3 — a brand offered for a specific Sub Asset (AssetType)."""

    sub_asset = models.ForeignKey(
        AssetType,
        on_delete=models.PROTECT,
        related_name="catalog_brands",
    )
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("sub_asset", "name")]
        verbose_name = "Catalogue Brand"
        verbose_name_plural = "Catalogue Brands"

    def __str__(self) -> str:
        return f"{self.name} ({self.sub_asset.name})"


class CatalogModel(models.Model):
    """Level 4 — a model offered under a specific Brand."""

    brand = models.ForeignKey(
        CatalogBrand,
        on_delete=models.PROTECT,
        related_name="catalog_models",
    )
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("brand", "name")]
        verbose_name = "Catalogue Model"
        verbose_name_plural = "Catalogue Models"

    def __str__(self) -> str:
        return f"{self.name} ({self.brand.name})"


class SubAssetSpecField(models.Model):
    """
    One specification field definition for a Sub Asset (AssetType).

    The ``widget`` drives how the asset form renders the field; ``options`` and
    ``unit`` configure that widget. This is the master-data replacement for the
    old hardcoded spec widgets + ``SpecChoice`` rows.
    """

    class Widget(models.TextChoices):
        TEXT = "text", "Text box"
        NUMBER = "number", "Number + fixed unit"
        UNITS = "units", "Number + unit chips"
        NUMBER_TOGGLE = "number_toggle", "Number + toggle / segmented chips"
        SELECT = "select", "Dropdown"
        TOGGLE = "toggle", "Toggle / segmented chips"

    sub_asset = models.ForeignKey(
        AssetType,
        on_delete=models.CASCADE,
        related_name="spec_fields",
    )
    key = models.CharField(
        max_length=60,
        help_text="Stable slug used as the storage key, e.g. ram, storage_type.",
    )
    label = models.CharField(max_length=120)
    widget = models.CharField(max_length=20, choices=Widget.choices, default=Widget.TEXT)
    # For NUMBER: a fixed unit badge (e.g. "GB", "inches", "cores").
    unit = models.CharField(max_length=20, blank=True)
    # For SELECT / TOGGLE / UNITS: the list of option strings.
    options = models.JSONField(default=list, blank=True)
    required = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        unique_together = [("sub_asset", "key")]
        verbose_name = "Spec Field"
        verbose_name_plural = "Spec Fields"

    def __str__(self) -> str:
        return f"{self.sub_asset.name} · {self.label}"

    def as_dict(self) -> dict:
        """Serialisable form used by the JSON API and the form renderer."""
        return {
            "key": self.key,
            "label": self.label,
            "widget": self.widget,
            "unit": self.unit,
            "options": list(self.options or []),
            "required": self.required,
        }


class ComponentType(models.Model):
    """
    Master data for the parts that can be fitted to an asset — RAM, Storage,
    an SFP module. Replaces the hardcoded ``AssetComponent.ComponentType``
    enum: the unit chips shown next to the capacity box come from ``units``,
    and ``applies_to`` decides which Sub Assets offer this part.

    ``applies_to`` is an explicit allow-list: a part is offered on the Sub
    Assets named there and **nowhere else**. An empty list therefore means the
    part is offered on no asset at all — it is inert until someone maps it.
    Mapping a part to a Sub Asset switches that Sub Asset's ``has_components``
    on, so master data stays the single control over which assets get a
    components panel.
    """

    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(
        max_length=40,
        unique=True,
        help_text="Stable key kept on the component row, e.g. ram, storage.",
    )
    # Unit chips offered next to the capacity box, e.g. ["GB", "TB"].
    units = models.JSONField(default=list, blank=True)
    default_unit = models.CharField(max_length=20, blank=True)
    capacity_required = models.BooleanField(
        default=True,
        help_text="Tick for sized parts (RAM, Storage). Untick for a keyboard or a mouse.",
    )
    serial_required = models.BooleanField(default=False)
    applies_to = models.ManyToManyField(
        AssetType,
        blank=True,
        related_name="component_types",
        help_text="Select the Sub Assets that take this part. An unmapped part is offered nowhere.",
    )
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Component Type"
        verbose_name_plural = "Component Types"

    def __str__(self) -> str:
        return self.name

    @property
    def unit_list(self) -> list[str]:
        return [str(u) for u in (self.units or [])]

    def clean(self) -> None:
        units = self.unit_list
        if self.default_unit and units and self.default_unit not in units:
            raise ValidationError(
                {"default_unit": f"“{self.default_unit}” is not one of the units: {', '.join(units)}."}
            )

    def as_dict(self) -> dict:
        """Serialisable form used by the JSON API and the component panel."""
        return {
            "id": self.pk,
            "name": self.name,
            "code": self.code,
            "units": self.unit_list,
            "default_unit": self.default_unit or (self.unit_list[0] if self.unit_list else ""),
            "capacity_required": self.capacity_required,
            "serial_required": self.serial_required,
        }

    def available_for(self, asset_type: AssetType | None) -> bool:
        """A part is offered only where it is explicitly mapped."""
        if asset_type is None:
            return False
        return self.applies_to.filter(pk=asset_type.pk).exists()


@receiver(m2m_changed, sender=ComponentType.applies_to.through)
def _enable_components_on_mapped_types(sender, instance, action, pk_set, reverse, **kwargs):
    """
    Mapping a part to a Sub Asset turns that Sub Asset's ``has_components`` on.

    Without this an Admin would have to remember to tick two boxes on two
    different sections of the Master Data page, and the components panel would
    stay hidden on an asset whose parts are already configured. Nothing is ever
    switched *off* here — un-mapping a part does not prove the Sub Asset has no
    other parts, and the flag is still editable by hand.
    """
    if action != "post_add" or not pk_set:
        return
    type_ids = {instance.pk} if reverse else set(pk_set)
    AssetType.objects.filter(pk__in=type_ids, has_components=False).update(has_components=True)
