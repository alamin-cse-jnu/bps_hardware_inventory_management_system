from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


class AuditSession(models.Model):
    """
    A physical inventory audit — an IT officer walks around scanning QR codes.
    Each scan creates an AuditScan row.
    The session produces found/misplaced/missing reports.
    """

    reference = models.CharField(max_length=50, unique=True)
    performed_by = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name="audit_sessions",
    )
    location = models.ForeignKey(
        "locations.Location",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_sessions",
        help_text="Leave blank for a full-inventory audit.",
    )
    note = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Audit Session"
        verbose_name_plural = "Audit Sessions"

    def __str__(self) -> str:
        return self.reference

    @classmethod
    def generate_reference(cls) -> str:
        year = timezone.now().year
        prefix = f"AUD-{year}-"
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
    def is_complete(self) -> bool:
        return self.completed_at is not None

    def complete(self) -> None:
        self.completed_at = timezone.now()
        self.save(update_fields=["completed_at", "updated_at"])


class AuditScan(models.Model):
    """
    Records one QR scan within an AuditSession.
    Each asset may appear at most once per session.
    """

    session = models.ForeignKey(
        AuditSession, on_delete=models.CASCADE,
        related_name="scans",
    )
    asset = models.ForeignKey(
        "assets.AssetItem", on_delete=models.PROTECT,
        related_name="audit_scans",
    )
    scanned_at = models.DateTimeField(auto_now_add=True)
    found_location = models.ForeignKey(
        "locations.Location",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_scans_found",
    )
    note = models.CharField(max_length=500, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("session", "asset")]
        ordering = ["-scanned_at"]
        verbose_name = "Audit Scan"
        verbose_name_plural = "Audit Scans"

    def __str__(self) -> str:
        return f"{self.session.reference} — {self.asset.asset_tag}"
