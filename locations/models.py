from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

User = get_user_model()


class Location(models.Model):
    class LevelType(models.TextChoices):
        BUILDING = "BUILDING", "Building"
        FLOOR = "FLOOR", "Floor"
        ROOM = "ROOM", "Room"

    name = models.CharField(max_length=200)
    name_bn = models.CharField(max_length=200, blank=True)
    level_type = models.CharField(max_length=10, choices=LevelType.choices)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="locations_created",
    )

    class Meta:
        ordering = ["level_type", "name"]
        verbose_name = "Location"
        verbose_name_plural = "Locations"

    def __str__(self) -> str:
        return self.full_path

    def clean(self) -> None:
        if self.level_type == self.LevelType.BUILDING:
            if self.parent_id is not None:
                raise ValidationError(
                    {"parent": "A building must not have a parent."}
                )
        elif self.level_type == self.LevelType.FLOOR:
            if self.parent_id is None:
                raise ValidationError(
                    {"parent": "A floor must belong to a building."}
                )
            if self.parent.level_type != self.LevelType.BUILDING:
                raise ValidationError(
                    {"parent": "A floor's parent must be a building."}
                )
        elif self.level_type == self.LevelType.ROOM:
            if self.parent_id is None:
                raise ValidationError(
                    {"parent": "A room must belong to a floor."}
                )
            if self.parent.level_type != self.LevelType.FLOOR:
                raise ValidationError(
                    {"parent": "A room's parent must be a floor."}
                )

    @property
    def full_path(self) -> str:
        """Walk the parent chain and return 'Building → Floor → Room'."""
        parts = [self.name]
        node = self
        while node.parent_id is not None:
            node = node.parent
            parts.append(node.name)
        parts.reverse()
        return " → ".join(parts)
