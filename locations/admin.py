from django.contrib import admin

from .models import Location


class LocationChildInline(admin.TabularInline):
    model = Location
    fk_name = "parent"
    fields = ("name", "name_bn", "level_type", "is_active")
    extra = 0
    show_change_link = True


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "name_bn", "level_type", "parent", "full_path", "is_active")
    list_filter = ("level_type", "is_active")
    search_fields = ("name", "name_bn")
    readonly_fields = ("full_path", "created_at", "updated_at")
    inlines = [LocationChildInline]

    fieldsets = (
        (None, {
            "fields": ("name", "name_bn", "level_type", "parent", "is_active"),
        }),
        ("Audit", {
            "fields": ("created_by", "full_path", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter parent dropdown to only valid parents based on URL hint."""
        if db_field.name == "parent":
            # Limit to buildings when creating floors, floors when creating rooms.
            # We read level_type from the submitted form data if available.
            level_type = None
            if request.method == "POST":
                level_type = request.POST.get("level_type")
            elif request.method == "GET":
                level_type = request.GET.get("level_type")

            if level_type == Location.LevelType.FLOOR:
                kwargs["queryset"] = Location.objects.filter(
                    level_type=Location.LevelType.BUILDING
                )
            elif level_type == Location.LevelType.ROOM:
                kwargs["queryset"] = Location.objects.filter(
                    level_type=Location.LevelType.FLOOR
                )
            else:
                # Default: show buildings and floors as possible parents
                kwargs["queryset"] = Location.objects.exclude(
                    level_type=Location.LevelType.ROOM
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
