from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "target_model", "target_label", "actor_label")
    list_filter = ("action", "target_model")
    search_fields = ("target_label", "actor_label", "note")
    date_hierarchy = "created_at"

    # Audit entries are immutable — read-only everywhere.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
