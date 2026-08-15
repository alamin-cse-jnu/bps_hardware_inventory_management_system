from django.contrib import admin

from .models import Block, Building, Level, Location


@admin.register(Building, Block, Level)
class DimensionAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "building", "block", "level", "room", "is_active")
    list_filter = ("is_active", "building", "block", "level")
    search_fields = ("name", "room")
    autocomplete_fields = ("building", "block", "level")
    readonly_fields = ("full_path", "created_at", "updated_at")

    fieldsets = (
        (None, {
            "fields": ("name", "building", "block", "level", "room", "is_active"),
        }),
        ("Audit", {
            "fields": ("created_by", "full_path", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
