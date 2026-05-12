from django.contrib import admin
from django.utils.html import format_html

from .models import Assignee, CachedEmployee, CachedMP, CachedOffice, Source


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _source_badge(source: str) -> str:
    if source == Source.PRP_API:
        return format_html(
            '<span style="padding:2px 8px;border-radius:99px;font-size:11px;'
            'font-weight:700;background:#eff6ff;color:#3b82f6;">PRP API</span>'
        )
    return format_html(
        '<span style="padding:2px 8px;border-radius:99px;font-size:11px;'
        'font-weight:700;background:#FBF5E6;color:#C8A951;">Manual</span>'
    )


def _active_badge(is_active: bool) -> str:
    if is_active:
        return format_html(
            '<span style="padding:2px 8px;border-radius:99px;font-size:11px;'
            'font-weight:700;background:#ecfdf5;color:#10b981;">Active</span>'
        )
    return format_html(
        '<span style="padding:2px 8px;border-radius:99px;font-size:11px;'
        'font-weight:700;background:#fef2f2;color:#ef4444;">Inactive</span>'
    )


# ── CachedEmployee ─────────────────────────────────────────────────────────────

@admin.register(CachedEmployee)
class CachedEmployeeAdmin(admin.ModelAdmin):
    list_display = [
        "name_en", "name_bn", "source_badge", "designation_display",
        "office_name_en", "active_badge", "last_seen_active",
    ]
    list_filter = ["source", "is_active"]
    search_fields = ["name_en", "name_bn", "section_name_en", "branch_name_en", "prp_id"]
    readonly_fields = ["prp_id", "created_at", "updated_at", "created_by", "last_seen_active", "inactive_since"]
    ordering = ["name_en"]
    list_per_page = 50

    fieldsets = [
        ("Identity", {
            "fields": ["prp_id", "source", "name_en", "name_bn", "gender", "photo_url"],
        }),
        ("Contact", {
            "fields": ["mobile", "telephone"],
        }),
        ("Office Placement", {
            "fields": [
                ("wing_id", "wing_name_en", "wing_name_bn"),
                ("branch_id", "branch_name_en", "branch_name_bn"),
                ("section_id", "section_name_en", "section_name_bn"),
                ("unit_id", "unit_name_en", "unit_name_bn"),
                ("office_id", "office_name_en", "office_name_bn"),
            ],
        }),
        ("Status", {
            "fields": ["is_active", "api_status", "inactive_since", "last_seen_active"],
        }),
        ("Metadata", {
            "fields": ["created_at", "updated_at", "created_by"],
            "classes": ["collapse"],
        }),
    ]

    @admin.display(description="Source")
    def source_badge(self, obj):
        return _source_badge(obj.source)

    @admin.display(description="Active")
    def active_badge(self, obj):
        return _active_badge(obj.is_active)

    @admin.display(description="Designation")
    def designation_display(self, obj):
        return obj.designation or "—"

    def get_readonly_fields(self, request, obj=None):
        ro = list(self.readonly_fields)
        if obj and obj.source == Source.PRP_API:
            ro += [
                "name_en", "name_bn", "mobile", "telephone", "gender",
                "wing_id", "wing_name_en", "wing_name_bn",
                "branch_id", "branch_name_en", "branch_name_bn",
                "section_id", "section_name_en", "section_name_bn",
                "unit_id", "unit_name_en", "unit_name_bn",
                "office_id", "office_name_en", "office_name_bn",
                "api_status",
            ]
        return ro

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ── CachedMP ───────────────────────────────────────────────────────────────────

@admin.register(CachedMP)
class CachedMPAdmin(admin.ModelAdmin):
    list_display = [
        "name_en", "name_bn", "parliament_no", "constituency",
        "source_badge", "active_badge", "last_seen_active",
    ]
    list_filter = ["source", "is_active", "parliament_no"]
    search_fields = ["name_en", "name_bn", "constituency", "prp_id"]
    readonly_fields = ["prp_id", "created_at", "updated_at", "created_by", "last_seen_active", "inactive_since"]
    ordering = ["name_en"]
    list_per_page = 50

    fieldsets = [
        ("Identity", {
            "fields": ["prp_id", "source", "name_en", "name_bn", "gender", "photo_url"],
        }),
        ("Parliamentary Details", {
            "fields": ["parliament_no", "constituency", "office_details_raw"],
        }),
        ("Contact", {
            "fields": ["mobile", "telephone"],
        }),
        ("Status", {
            "fields": ["is_active", "api_status", "inactive_since", "last_seen_active"],
        }),
        ("Metadata", {
            "fields": ["created_at", "updated_at", "created_by"],
            "classes": ["collapse"],
        }),
    ]

    @admin.display(description="Source")
    def source_badge(self, obj):
        return _source_badge(obj.source)

    @admin.display(description="Active")
    def active_badge(self, obj):
        return _active_badge(obj.is_active)

    def get_readonly_fields(self, request, obj=None):
        ro = list(self.readonly_fields)
        if obj and obj.source == Source.PRP_API:
            ro += [
                "name_en", "name_bn", "parliament_no", "constituency",
                "mobile", "telephone", "gender", "office_details_raw", "api_status",
            ]
        return ro

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ── CachedOffice ───────────────────────────────────────────────────────────────

@admin.register(CachedOffice)
class CachedOfficeAdmin(admin.ModelAdmin):
    list_display = [
        "name_en", "name_bn", "parent_prp_id", "is_abstract",
        "source_badge", "active_badge",
    ]
    list_filter = ["source", "is_active", "is_abstract"]
    search_fields = ["name_en", "name_bn", "prp_id"]
    readonly_fields = ["prp_id", "created_at", "updated_at", "created_by", "last_seen_active", "inactive_since"]
    ordering = ["name_en"]
    list_per_page = 50

    fieldsets = [
        ("Identity", {
            "fields": ["prp_id", "parent_prp_id", "source", "name_en", "name_bn", "is_abstract"],
        }),
        ("Status", {
            "fields": ["is_active", "inactive_since", "last_seen_active"],
        }),
        ("Metadata", {
            "fields": ["created_at", "updated_at", "created_by"],
            "classes": ["collapse"],
        }),
    ]

    @admin.display(description="Source")
    def source_badge(self, obj):
        return _source_badge(obj.source)

    @admin.display(description="Active")
    def active_badge(self, obj):
        return _active_badge(obj.is_active)

    def get_readonly_fields(self, request, obj=None):
        ro = list(self.readonly_fields)
        if obj and obj.source == Source.PRP_API:
            ro += ["name_en", "name_bn", "parent_prp_id", "is_abstract"]
        return ro

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ── Assignee ───────────────────────────────────────────────────────────────────

@admin.register(Assignee)
class AssigneeAdmin(admin.ModelAdmin):
    list_display = [
        "display_name_col", "assignee_type", "source_badge", "active_badge", "created_at",
    ]
    list_filter = ["assignee_type", "is_active"]
    search_fields = [
        "employee__name_en", "mp__name_en", "office__name_en", "location__name",
    ]
    readonly_fields = ["created_at", "updated_at", "created_by"]
    ordering = ["assignee_type"]
    list_per_page = 50

    fieldsets = [
        ("Type", {
            "fields": ["assignee_type", "is_active"],
        }),
        ("Holder (set exactly one)", {
            "fields": ["employee", "mp", "office", "location"],
            "description": "Set exactly one field to match the assignee_type above.",
        }),
        ("Metadata", {
            "fields": ["created_at", "updated_at", "created_by"],
            "classes": ["collapse"],
        }),
    ]

    @admin.display(description="Name")
    def display_name_col(self, obj):
        return obj.display_name

    @admin.display(description="Source")
    def source_badge(self, obj):
        src = obj.holder_source
        return _source_badge(src) if src else format_html(
            '<span style="color:#9ca3af;font-size:11px;">—</span>'
        )

    @admin.display(description="Active")
    def active_badge(self, obj):
        return _active_badge(obj.is_active)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
