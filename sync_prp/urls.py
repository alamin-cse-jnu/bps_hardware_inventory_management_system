from django.urls import path

from . import views

app_name = "sync_prp"

urlpatterns = [
    path("trigger/", views.trigger_sync, name="trigger"),
    path("status/", views.sync_status, name="status"),
]
