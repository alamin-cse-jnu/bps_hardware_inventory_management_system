from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class SyncLog(models.Model):
    class Status(models.TextChoices):
        RUNNING = "RUNNING", "Running"
        SUCCESS = "SUCCESS", "Success"
        PARTIAL = "PARTIAL", "Partial"
        FAILED = "FAILED", "Failed"

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.RUNNING,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    employees_added = models.IntegerField(default=0)
    employees_updated = models.IntegerField(default=0)
    employees_flagged = models.IntegerField(default=0)
    mps_added = models.IntegerField(default=0)
    mps_updated = models.IntegerField(default=0)
    mps_flagged = models.IntegerField(default=0)
    offices_added = models.IntegerField(default=0)
    offices_updated = models.IntegerField(default=0)
    offices_flagged = models.IntegerField(default=0)

    error_message = models.TextField(blank=True)
    triggered_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="sync_logs",
    )

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "Sync Log"
        verbose_name_plural = "Sync Logs"

    def __str__(self) -> str:
        return f"Sync {self.started_at:%Y-%m-%d %H:%M} [{self.status}]"

    @property
    def total_added(self) -> int:
        return self.employees_added + self.mps_added + self.offices_added

    @property
    def total_updated(self) -> int:
        return self.employees_updated + self.mps_updated + self.offices_updated

    @property
    def total_flagged(self) -> int:
        return self.employees_flagged + self.mps_flagged + self.offices_flagged

    @property
    def duration_seconds(self) -> float | None:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
