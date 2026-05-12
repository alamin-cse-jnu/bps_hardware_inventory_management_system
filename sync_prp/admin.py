from django.contrib import admin
from django.utils.html import format_html

from .models import SyncLog


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = [
        "started_at", "status_badge", "triggered_by",
        "col_employees", "col_mps", "col_offices",
        "total_flagged_col", "duration_display",
    ]
    list_filter = ["status"]
    readonly_fields = [
        "status", "started_at", "completed_at", "triggered_by",
        "employees_added", "employees_updated", "employees_flagged",
        "mps_added", "mps_updated", "mps_flagged",
        "offices_added", "offices_updated", "offices_flagged",
        "error_message",
    ]
    ordering = ["-started_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Status")
    def status_badge(self, obj):
        styles = {
            SyncLog.Status.RUNNING: ("#F59E0B", "#FFFBEB"),
            SyncLog.Status.SUCCESS: ("#10B981", "#ECFDF5"),
            SyncLog.Status.PARTIAL: ("#F59E0B", "#FFFBEB"),
            SyncLog.Status.FAILED:  ("#EF4444", "#FEF2F2"),
        }
        fg, bg = styles.get(obj.status, ("#6B7280", "#F3F4F6"))
        return format_html(
            '<span style="background:{};color:{};padding:2px 10px;'
            'border-radius:99px;font-size:11px;font-weight:700;">{}</span>',
            bg, fg, obj.get_status_display(),
        )

    @admin.display(description="Employees (+/~/!)")
    def col_employees(self, obj):
        return f"+{obj.employees_added} ~{obj.employees_updated} !{obj.employees_flagged}"

    @admin.display(description="MPs (+/~/!)")
    def col_mps(self, obj):
        return f"+{obj.mps_added} ~{obj.mps_updated} !{obj.mps_flagged}"

    @admin.display(description="Offices (+/~/!)")
    def col_offices(self, obj):
        return f"+{obj.offices_added} ~{obj.offices_updated} !{obj.offices_flagged}"

    @admin.display(description="Flagged")
    def total_flagged_col(self, obj):
        n = obj.total_flagged
        if n > 0:
            return format_html(
                '<span style="color:#EF4444;font-weight:700;">{}</span>', n
            )
        return "0"

    @admin.display(description="Duration")
    def duration_display(self, obj):
        secs = obj.duration_seconds
        if secs is None:
            return "—"
        return f"{secs:.1f}s" if secs < 60 else f"{secs / 60:.1f}m"
