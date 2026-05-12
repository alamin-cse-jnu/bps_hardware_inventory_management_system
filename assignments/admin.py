from django.contrib import admin
from django.utils.html import format_html

from .models import AlertStatus, Assignment, InactiveHolderAlert, TransferBatch


# ── TransferBatch ──────────────────────────────────────────────────────────────

class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 0
    fields = ["asset", "assignee", "assigned_at", "returned_at", "notes"]
    readonly_fields = ["asset", "assignee", "assigned_at", "returned_at"]
    can_delete = False
    show_change_link = True


@admin.register(TransferBatch)
class TransferBatchAdmin(admin.ModelAdmin):
    list_display = ["reference", "performed_by", "assignment_count", "note_preview", "created_at"]
    search_fields = ["reference", "performed_by__username", "note"]
    readonly_fields = ["reference", "created_at", "updated_at"]
    ordering = ["-created_at"]
    list_per_page = 30
    inlines = [AssignmentInline]

    fieldsets = [
        (None, {
            "fields": ["reference", "performed_by", "note"],
        }),
        ("Metadata", {
            "fields": ["created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]

    @admin.display(description="Assignments")
    def assignment_count(self, obj):
        n = obj.assignments.count()
        return format_html(
            '<span style="font-weight:700;color:#006633;">{}</span>', n
        )

    @admin.display(description="Note")
    def note_preview(self, obj):
        return (obj.note[:60] + "…") if len(obj.note) > 60 else obj.note or "—"


# ── Assignment ─────────────────────────────────────────────────────────────────

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = [
        "asset_tag_col", "assignee_name_col", "assigned_at",
        "status_badge", "performed_by", "batch",
    ]
    list_filter = ["assignee__assignee_type"]
    search_fields = [
        "asset__asset_tag", "asset__brand", "asset__model_name",
        "assignee__employee__name_en", "assignee__mp__name_en",
        "assignee__office__name_en",
    ]
    readonly_fields = [
        "asset", "assignee", "assigned_at", "returned_at",
        "holder_snapshot", "performed_by", "batch", "created_at", "updated_at",
    ]
    ordering = ["-assigned_at"]
    list_per_page = 50
    date_hierarchy = "assigned_at"

    fieldsets = [
        ("Assignment", {
            "fields": ["asset", "assignee", "assigned_at", "returned_at"],
        }),
        ("Holder Snapshot (frozen at assignment time)", {
            "fields": ["holder_snapshot"],
            "classes": ["collapse"],
        }),
        ("Details", {
            "fields": ["performed_by", "batch", "notes"],
        }),
        ("Metadata", {
            "fields": ["created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Asset Tag")
    def asset_tag_col(self, obj):
        return format_html(
            '<span style="font-family:\'JetBrains Mono\',monospace;'
            'font-size:12px;font-weight:700;color:#006633;">{}</span>',
            obj.asset.asset_tag,
        )

    @admin.display(description="Assignee")
    def assignee_name_col(self, obj):
        snapshot = obj.holder_snapshot or {}
        name = snapshot.get("display_name", str(obj.assignee))
        dept = snapshot.get("department") or snapshot.get("designation", "")
        if dept:
            return format_html(
                '<span style="font-weight:600;">{}</span>'
                '<br><span style="font-size:11px;color:#6c757d;">{}</span>',
                name, dept,
            )
        return name

    @admin.display(description="Status")
    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="padding:2px 8px;border-radius:99px;font-size:11px;'
                'font-weight:700;background:#eff6ff;color:#3b82f6;">Active</span>'
            )
        return format_html(
            '<span style="padding:2px 8px;border-radius:99px;font-size:11px;'
            'font-weight:700;background:#f3f4f6;color:#6b7280;">Returned</span>'
        )

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related("asset", "assignee", "performed_by", "batch")
        )


# ── InactiveHolderAlert ────────────────────────────────────────────────────────

@admin.register(InactiveHolderAlert)
class InactiveHolderAlertAdmin(admin.ModelAdmin):
    list_display = [
        "assignee_name_col", "raised_at", "status_badge",
        "active_assignments_col", "resolved_at", "resolved_by",
    ]
    list_filter = ["status"]
    search_fields = [
        "assignee__employee__name_en", "assignee__mp__name_en",
        "assignee__office__name_en",
    ]
    readonly_fields = [
        "assignee", "raised_at", "created_at", "updated_at",
        "resolved_at", "resolved_by",
    ]
    ordering = ["-raised_at"]
    list_per_page = 30

    fieldsets = [
        ("Alert", {
            "fields": ["assignee", "raised_at", "status"],
        }),
        ("Resolution", {
            "fields": ["resolved_at", "resolved_by", "note"],
        }),
        ("Metadata", {
            "fields": ["created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]

    @admin.display(description="Holder")
    def assignee_name_col(self, obj):
        return obj.assignee.display_name

    @admin.display(description="Status")
    def status_badge(self, obj):
        colours = {
            AlertStatus.OPEN: ("background:#fef2f2;color:#ef4444;", "Open"),
            AlertStatus.RESOLVED: ("background:#ecfdf5;color:#10b981;", "Resolved"),
            AlertStatus.DISMISSED: ("background:#f3f4f6;color:#6b7280;", "Dismissed"),
        }
        style, label = colours.get(obj.status, ("", obj.status))
        return format_html(
            '<span style="padding:2px 8px;border-radius:99px;font-size:11px;'
            'font-weight:700;{}">{}</span>',
            style, label,
        )

    @admin.display(description="Active Assignments")
    def active_assignments_col(self, obj):
        from assignments.models import Assignment as Asgn
        count = Asgn.objects.filter(
            assignee=obj.assignee, returned_at__isnull=True
        ).count()
        color = "#ef4444" if count > 0 else "#10b981"
        return format_html(
            '<span style="font-weight:700;color:{};">{}</span>', color, count
        )

    def save_model(self, request, obj, form, change):
        if change and obj.status in (AlertStatus.RESOLVED, AlertStatus.DISMISSED):
            if not obj.resolved_by:
                obj.resolved_by = request.user
            from django.utils import timezone
            if not obj.resolved_at:
                obj.resolved_at = timezone.now()
        super().save_model(request, obj, form, change)
