from django.apps import AppConfig


class AssignmentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "assignments"

    def ready(self):
        # Connect signal handlers once the app registry is populated.
        from . import signals  # noqa: F401
