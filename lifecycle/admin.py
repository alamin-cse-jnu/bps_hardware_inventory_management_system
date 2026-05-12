from django.contrib import admin
from django.utils.html import format_html

from .models import EventType, LifecycleEvent

_EVENT_COLOURS = {
    EventType.MAINTENANCE_SENT:   ("background:#FFFBEB;color:#F59E0B;", "Maintenance"),
    EventType.MAINTENANCE_RETURN: ("background:#ECFDF5;color:#10B981;", "Return"),
    EventType.LOST:               ("background:#FEF2F2;color:#EF4444;", "Lost"),
    EventType.DAMAGED:            ("background:#FEF2F2;color:#EF4444;", "Damaged"),
    EventType.RECOVERED:          ("background:#ECFDF5;color:#10B981;", "Recovered"),
    EventType.REPAIRED:           ("background:#ECFDF5;color:#10B981;", "Repaired"),
    EventType.DISPOSED:           ("background:#F3F4F6;color:#9CA3AF;", "Disposed"),
    EventType.COMPONENT_SWAP:     ("background:#EFF6FF;color:#3B82F6;", "Component Swap"),
}


@admin.register(LifecycleEvent)
class LifecycleEventAdmin(admin.ModelAdmin):
    list_display = [
        "asset_tag_col", "event_badge", "old_status", "new_status",
        "performed_by", "occurred_at", "note_preview",
    ]
    list_filter = ["event_type"]
    search_fields = ["asset__asset_tag", "asset__brand", "asset__model_name", "performed_by__username"]
    readonly_fields = [
        "asset", "event_type", "old_status", "new_status",
        "performed_by", "component", "occurred_at", "created_at", "updated_at",
    ]
    ordering = ["-occurred_at"]
    date_hierarchy = "occurred_at"
    list_per_page = 50

    fieldsets = [
        ("Event", {"fields": ["asset", "event_type", "old_status", "new_status", "occurred_at"]}),
        ("Details", {"fields": ["performed_by", "note", "component"]}),
        ("Metadata", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Asset Tag")
    def asset_tag_col(self, obj):
        return format_html(
            '<span style="font-family:\'JetBrains Mono\',monospace;font-size:12px;'
            'font-weight:700;color:#006633;">{}</span>',
            obj.asset.asset_tag,
        )

    @admin.display(description="Event")
    def event_badge(self, obj):
        style, label = _EVENT_COLOURS.get(obj.event_type, ("", obj.event_type))
        return format_html(
            '<span style="padding:2px 8px;border-radius:99px;font-size:11px;'
            'font-weight:700;{}">{}</span>',
            style, label,
        )

    @admin.display(description="Note")
    def note_preview(self, obj):
        if not obj.note:
            return "—"
        return (obj.note[:60] + "…") if len(obj.note) > 60 else obj.note

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("asset", "performed_by", "component")
