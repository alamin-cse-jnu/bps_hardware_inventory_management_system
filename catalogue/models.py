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

from django.db import models

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
    widget = models.CharField(max_length=12, choices=Widget.choices, default=Widget.TEXT)
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
