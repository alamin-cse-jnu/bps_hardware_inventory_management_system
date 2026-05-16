from django.urls import path

from . import views

app_name = "sync_prp"

urlpatterns = [
    path("", views.sync_dashboard, name="dashboard"),
    path("trigger/", views.trigger_sync_view, name="trigger"),
    path("log/<int:pk>/", views.sync_log_detail, name="log_detail"),
    path("api/trigger/", views.trigger_sync, name="api_trigger"),
    path("api/status/", views.sync_status, name="status"),
]
