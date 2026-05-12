from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


class EventType(models.TextChoices):
    MAINTENANCE_SENT   = "MAINTENANCE_SENT",   "Sent to Maintenance"
    MAINTENANCE_RETURN = "MAINTENANCE_RETURN",  "Returned from Maintenance"
    LOST               = "LOST",               "Reported Lost"
    DAMAGED            = "DAMAGED",            "Reported Damaged"
    RECOVERED          = "RECOVERED",          "Recovered (Found)"
    REPAIRED           = "REPAIRED",           "Repaired"
    DISPOSED           = "DISPOSED",           "Disposed"
    COMPONENT_SWAP     = "COMPONENT_SWAP",     "Component Swap"


class LifecycleEvent(models.Model):
    """
    Records every non-ownership state change for an asset.

    For status-changing events, old_status and new_status capture the
    transition for the audit trail (asset.status has already changed by the
    time the row is saved).

    For COMPONENT_SWAP the status fields are identical — the component FK
    points to the newly-installed AssetComponent.
    """

    asset = models.ForeignKey(
        "assets.AssetItem",
        on_delete=models.PROTECT,
        related_name="lifecycle_events",
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)

    performed_by = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name="lifecycle_events_performed",
    )
    note = models.TextField(blank=True)

    # Only populated for COMPONENT_SWAP events; points to the new component
    component = models.ForeignKey(
        "assets.AssetComponent",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="swap_events",
    )

    occurred_at = models.DateTimeField(default=timezone.now)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name = "Lifecycle Event"
        verbose_name_plural = "Lifecycle Events"
        indexes = [
            models.Index(fields=["asset", "occurred_at"]),
            models.Index(fields=["event_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_event_type_display()} — {self.asset.asset_tag} ({self.occurred_at:%Y-%m-%d})"
