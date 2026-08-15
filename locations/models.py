from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

User = get_user_model()


class _NamedLookup(models.Model):
    """Shared base for the three independent location dimensions.

    Building / Block / Level are flat master-data lists with no relationship
    to one another. A Location references any combination of them.
    """

    name = models.CharField(max_length=200, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="%(class)ss_created",
    )

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Building(_NamedLookup):
    class Meta(_NamedLookup.Meta):
        verbose_name = "Building"
        verbose_name_plural = "Buildings"


class Block(_NamedLookup):
    class Meta(_NamedLookup.Meta):
        verbose_name = "Block"
        verbose_name_plural = "Blocks"


class Level(_NamedLookup):
    class Meta(_NamedLookup.Meta):
        verbose_name = "Level"
        verbose_name_plural = "Levels"


class Location(models.Model):
    """A physical location: a named place tagged with any combination of the
    three independent dimensions (Building / Block / Level) plus an optional
    room. At least one of building / block / level must be set."""

    name = models.CharField(max_length=200)
    building = models.ForeignKey(
        Building, null=True, blank=True, on_delete=models.PROTECT,
        related_name="locations",
    )
    block = models.ForeignKey(
        Block, null=True, blank=True, on_delete=models.PROTECT,
        related_name="locations",
    )
    level = models.ForeignKey(
        Level, null=True, blank=True, on_delete=models.PROTECT,
        related_name="locations",
    )
    room = models.CharField(max_length=100, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="locations_created",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Location"
        verbose_name_plural = "Locations"

    def __str__(self) -> str:
        return self.full_path

    def clean(self) -> None:
        if not self.name or not self.name.strip():
            raise ValidationError({"name": "Location name is required."})
        if not (self.building_id or self.block_id or self.level_id):
            raise ValidationError(
                "Select at least one of Building, Block or Level."
            )

    # ── Display helpers ───────────────────────────────────────────────────────

    @property
    def descriptor(self) -> str:
        """The set dimensions joined for display, e.g.
        'Main Building · Level-2 · South Block · Room 101'."""
        parts = []
        if self.building_id:
            parts.append(self.building.name)
        if self.level_id:
            parts.append(self.level.name)
        if self.block_id:
            parts.append(self.block.name)
        if self.room:
            parts.append(f"Room {self.room}")
        return " · ".join(parts)

    @property
    def full_path(self) -> str:
        """Full human label — name with its dimensions. Kept under this name so
        the assignee layer, reports and exports need no changes."""
        desc = self.descriptor
        return f"{self.name} — {desc}" if desc else self.name

    # ── Assignee layer sync ───────────────────────────────────────────────────

    def sync_assignee(self) -> None:
        """
        Mirror ``is_active`` onto the unified Assignee row, creating it if absent.

        A LOCATION assignee has no independent lifecycle — its active state is
        purely derived from the Location. The three cached holder types cascade
        the same way from their ``mark_inactive()``; locations toggle in both
        directions because the edit form exposes an is_active checkbox, so this
        must run on every save, not only on deactivation.
        """
        from assignees.models import Assignee, AssigneeType

        Assignee.objects.update_or_create(
            assignee_type=AssigneeType.LOCATION,
            location=self,
            defaults={"is_active": self.is_active},
        )
