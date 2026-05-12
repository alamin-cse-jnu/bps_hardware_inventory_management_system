from django.contrib import admin
from django.utils.html import format_html

from .models import AuditScan, AuditSession


class AuditScanInline(admin.TabularInline):
    model = AuditScan
    extra = 0
    fields = ["asset", "scanned_at", "found_location", "note"]
    readonly_fields = ["asset", "scanned_at"]
    can_delete = False


@admin.register(AuditSession)
class AuditSessionAdmin(admin.ModelAdmin):
    list_display = [
        "reference", "performed_by", "location", "scan_count_col",
        "status_badge", "created_at",
    ]
    search_fields = ["reference", "performed_by__username"]
    readonly_fields = ["reference", "created_at", "updated_at"]
    ordering = ["-created_at"]
    list_per_page = 30
    inlines = [AuditScanInline]

    fieldsets = [
        (None, {"fields": ["reference", "performed_by", "location", "note"]}),
        ("Completion", {"fields": ["completed_at"]}),
        ("Metadata", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]

    @admin.display(description="Scans")
    def scan_count_col(self, obj):
        n = obj.scans.count()
        return format_html('<span style="font-weight:700;color:#006633;">{}</span>', n)

    @admin.display(description="Status")
    def status_badge(self, obj):
        if obj.is_complete:
            return format_html(
                '<span style="padding:2px 8px;border-radius:99px;font-size:11px;'
                'font-weight:700;background:#ECFDF5;color:#10B981;">Complete</span>'
            )
        return format_html(
            '<span style="padding:2px 8px;border-radius:99px;font-size:11px;'
            'font-weight:700;background:#FFFBEB;color:#F59E0B;">In Progress</span>'
        )


@admin.register(AuditScan)
class AuditScanAdmin(admin.ModelAdmin):
    list_display = ["session", "asset_tag_col", "scanned_at", "found_location"]
    search_fields = ["session__reference", "asset__asset_tag"]
    readonly_fields = ["session", "asset", "scanned_at", "created_at", "updated_at"]
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    @admin.display(description="Asset Tag")
    def asset_tag_col(self, obj):
        return format_html(
            '<span style="font-family:\'JetBrains Mono\',monospace;'
            'font-size:12px;font-weight:700;color:#006633;">{}</span>',
            obj.asset.asset_tag,
        )
