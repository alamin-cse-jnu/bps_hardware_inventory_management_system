from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


class AuditLog(models.Model):
    """
    Immutable record of a single mutating action: what, before → after, who, when.

    The target is stored denormalised (``target_model`` / ``target_id`` /
    ``target_label``) rather than via a GenericForeignKey — consistent with this
    project's architecture and so the entry survives deletion of its target.
    """

    class Action(models.TextChoices):
        CREATE   = "CREATE",   "Created"
        UPDATE   = "UPDATE",   "Updated"
        DELETE   = "DELETE",   "Deleted"
        RESTORE  = "RESTORE",  "Restored"
        STATUS   = "STATUS",   "Status Changed"
        ASSIGN   = "ASSIGN",   "Assigned"
        RETURN   = "RETURN",   "Returned"

    actor = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_entries",
    )
    # Frozen display name — survives user deletion and renders "System" for
    # actor-less (sync / command) actions.
    actor_label = models.CharField(max_length=150, blank=True)

    action = models.CharField(max_length=20, choices=Action.choices)

    target_model = models.CharField(max_length=100)   # e.g. "assets.AssetItem"
    target_id    = models.CharField(max_length=64, blank=True)
    target_label = models.CharField(max_length=255, blank=True)

    # {field_name: [before, after]}
    changes = models.JSONField(default=dict, blank=True)
    note    = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Audit Entry"
        verbose_name_plural = "Audit Trail"
        indexes = [
            models.Index(fields=["target_model", "target_id"]),
            models.Index(fields=["action"]),
            models.Index(fields=["actor"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_action_display()} {self.target_label} by {self.actor_label}"
