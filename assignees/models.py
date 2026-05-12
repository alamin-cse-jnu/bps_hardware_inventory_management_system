from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Shared choices
# ─────────────────────────────────────────────────────────────────────────────

class Source(models.TextChoices):
    PRP_API = "PRP_API", "PRP API"
    MANUAL = "MANUAL", "Manual"


# ─────────────────────────────────────────────────────────────────────────────
# CachedEmployee
# ─────────────────────────────────────────────────────────────────────────────

class CachedEmployee(models.Model):
    """
    Local cache of an employee record.
    PRP_API records are owned by the sync process; MANUAL records are created
    by IT Officers and are completely invisible to sync (architectural decision #7).
    """

    # Identity
    prp_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.PRP_API)

    # Names
    name_en = models.CharField(max_length=200)
    name_bn = models.CharField(max_length=200, blank=True)

    # Contact
    mobile = models.CharField(max_length=30, blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    photo_url = models.TextField(blank=True)
    api_status = models.CharField(max_length=50, blank=True)

    # Office placement (from officeDetails in API response)
    wing_id = models.CharField(max_length=50, blank=True)
    wing_name_en = models.CharField(max_length=200, blank=True)
    wing_name_bn = models.CharField(max_length=200, blank=True)
    branch_id = models.CharField(max_length=50, blank=True)
    branch_name_en = models.CharField(max_length=200, blank=True)
    branch_name_bn = models.CharField(max_length=200, blank=True)
    section_id = models.CharField(max_length=50, blank=True)
    section_name_en = models.CharField(max_length=200, blank=True)
    section_name_bn = models.CharField(max_length=200, blank=True)
    unit_id = models.CharField(max_length=50, blank=True)
    unit_name_en = models.CharField(max_length=200, blank=True)
    unit_name_bn = models.CharField(max_length=200, blank=True)
    office_id = models.CharField(max_length=50, blank=True)
    office_name_en = models.CharField(max_length=200, blank=True)
    office_name_bn = models.CharField(max_length=200, blank=True)

    # Activity tracking
    is_active = models.BooleanField(default=True)
    inactive_since = models.DateTimeField(null=True, blank=True)
    last_seen_active = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="employees_created",
    )

    class Meta:
        ordering = ["name_en"]
        verbose_name = "Cached Employee"
        verbose_name_plural = "Cached Employees"
        indexes = [
            models.Index(fields=["source", "is_active"]),
            models.Index(fields=["name_en"]),
        ]

    def __str__(self) -> str:
        return f"{self.name_en} ({self.get_source_display()})"

    @property
    def designation(self) -> str:
        """Build 'Section, Branch, Wing' designation string for snapshots."""
        parts = [
            p for p in [self.section_name_en, self.branch_name_en, self.wing_name_en]
            if p
        ]
        return ", ".join(parts)

    def mark_inactive(self) -> None:
        self.is_active = False
        self.inactive_since = timezone.now()
        self.save(update_fields=["is_active", "inactive_since", "updated_at"])


# ─────────────────────────────────────────────────────────────────────────────
# CachedMP
# ─────────────────────────────────────────────────────────────────────────────

class CachedMP(models.Model):
    """
    Local cache of a Member of Parliament record.
    Same dual-source rules as CachedEmployee.
    """

    prp_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.PRP_API)

    parliament_no = models.IntegerField(null=True, blank=True)
    constituency = models.CharField(max_length=200, blank=True)

    name_en = models.CharField(max_length=200)
    name_bn = models.CharField(max_length=200, blank=True)
    mobile = models.CharField(max_length=30, blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    photo_url = models.TextField(blank=True)
    api_status = models.CharField(max_length=50, blank=True)

    # API returns officeDetails as a raw string for MPs
    office_details_raw = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    inactive_since = models.DateTimeField(null=True, blank=True)
    last_seen_active = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="mps_created",
    )

    class Meta:
        ordering = ["name_en"]
        verbose_name = "Cached MP"
        verbose_name_plural = "Cached MPs"
        indexes = [
            models.Index(fields=["source", "is_active"]),
            models.Index(fields=["parliament_no"]),
        ]

    def __str__(self) -> str:
        parl = f" (Parliament {self.parliament_no})" if self.parliament_no else ""
        return f"{self.name_en}{parl}"

    @property
    def designation(self) -> str:
        parts = [p for p in [self.constituency, self.office_details_raw] if p]
        return ", ".join(parts) if parts else "Member of Parliament"

    def mark_inactive(self) -> None:
        self.is_active = False
        self.inactive_since = timezone.now()
        self.save(update_fields=["is_active", "inactive_since", "updated_at"])


# ─────────────────────────────────────────────────────────────────────────────
# CachedOffice
# ─────────────────────────────────────────────────────────────────────────────

class CachedOffice(models.Model):
    """
    Local cache of an office/department record from PRP API.
    parent_prp_id mirrors the API's parentId to reconstruct hierarchy.
    """

    prp_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    parent_prp_id = models.CharField(max_length=100, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.PRP_API)

    name_en = models.CharField(max_length=300)
    name_bn = models.CharField(max_length=300, blank=True)
    is_abstract = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    inactive_since = models.DateTimeField(null=True, blank=True)
    last_seen_active = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="offices_created",
    )

    class Meta:
        ordering = ["name_en"]
        verbose_name = "Cached Office"
        verbose_name_plural = "Cached Offices"
        indexes = [
            models.Index(fields=["source", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.name_en

    def mark_inactive(self) -> None:
        self.is_active = False
        self.inactive_since = timezone.now()
        self.save(update_fields=["is_active", "inactive_since", "updated_at"])


# ─────────────────────────────────────────────────────────────────────────────
# Assignee (unified holder — architectural decision #2)
# ─────────────────────────────────────────────────────────────────────────────

class AssigneeType(models.TextChoices):
    EMPLOYEE = "EMPLOYEE", "Employee"
    MP = "MP", "MP (Member of Parliament)"
    OFFICE = "OFFICE", "Office / Department"
    LOCATION = "LOCATION", "Location (Storage)"


class Assignee(models.Model):
    """
    Unified holder row. Exactly one of the four FK fields is populated,
    determined by assignee_type. No GenericForeignKey — all queries use
    one JOIN (architectural decision #2).
    """

    assignee_type = models.CharField(max_length=10, choices=AssigneeType.choices)

    employee = models.ForeignKey(
        CachedEmployee, null=True, blank=True,
        on_delete=models.PROTECT,
        related_name="assignee_records",
    )
    mp = models.ForeignKey(
        CachedMP, null=True, blank=True,
        on_delete=models.PROTECT,
        related_name="assignee_records",
    )
    office = models.ForeignKey(
        CachedOffice, null=True, blank=True,
        on_delete=models.PROTECT,
        related_name="assignee_records",
    )
    location = models.ForeignKey(
        "locations.Location", null=True, blank=True,
        on_delete=models.PROTECT,
        related_name="assignee_records",
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="assignees_created",
    )

    class Meta:
        ordering = ["assignee_type"]
        verbose_name = "Assignee"
        verbose_name_plural = "Assignees"
        indexes = [
            models.Index(fields=["assignee_type", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.display_name} ({self.get_assignee_type_display()})"

    # ── Validation ────────────────────────────────────────────────────────────

    def clean(self) -> None:
        type_to_field = {
            AssigneeType.EMPLOYEE: "employee",
            AssigneeType.MP: "mp",
            AssigneeType.OFFICE: "office",
            AssigneeType.LOCATION: "location",
        }
        all_fields = list(type_to_field.values())
        expected_field = type_to_field.get(self.assignee_type)

        if expected_field is None:
            raise ValidationError({"assignee_type": "Invalid assignee type."})

        # Required FK must be set
        if getattr(self, f"{expected_field}_id") is None:
            raise ValidationError(
                {expected_field: f"An assignee of type '{self.assignee_type}' requires a {expected_field}."}
            )

        # All other FKs must be null
        for field in all_fields:
            if field != expected_field and getattr(self, f"{field}_id") is not None:
                raise ValidationError(
                    {field: f"Cannot set '{field}' when assignee_type is '{self.assignee_type}'."}
                )

    # ── Display helpers ───────────────────────────────────────────────────────

    @property
    def display_name(self) -> str:
        if self.assignee_type == AssigneeType.EMPLOYEE and self.employee_id:
            return self.employee.name_en
        if self.assignee_type == AssigneeType.MP and self.mp_id:
            return self.mp.name_en
        if self.assignee_type == AssigneeType.OFFICE and self.office_id:
            return self.office.name_en
        if self.assignee_type == AssigneeType.LOCATION and self.location_id:
            return self.location.full_path
        return "Unknown"

    @property
    def holder_source(self) -> str:
        """Returns the source (PRP_API / MANUAL) of the underlying holder, or '' for Location."""
        if self.assignee_type == AssigneeType.EMPLOYEE and self.employee_id:
            return self.employee.source
        if self.assignee_type == AssigneeType.MP and self.mp_id:
            return self.mp.source
        if self.assignee_type == AssigneeType.OFFICE and self.office_id:
            return self.office.source
        return ""

    def build_snapshot(self) -> dict:
        """
        Freeze a snapshot of holder details at assignment time (architectural decision #4).
        This dict is stored in Assignment.holder_snapshot and never changes.
        """
        snapshot: dict = {
            "assignee_type": self.assignee_type,
            "display_name": self.display_name,
            "designation": "",
            "department": "",
            "source": self.holder_source,
        }
        if self.assignee_type == AssigneeType.EMPLOYEE and self.employee_id:
            emp = self.employee
            snapshot["designation"] = emp.designation
            snapshot["department"] = emp.office_name_en
        elif self.assignee_type == AssigneeType.MP and self.mp_id:
            snapshot["designation"] = self.mp.designation
        elif self.assignee_type == AssigneeType.LOCATION and self.location_id:
            snapshot["designation"] = self.location.full_path
        return snapshot
