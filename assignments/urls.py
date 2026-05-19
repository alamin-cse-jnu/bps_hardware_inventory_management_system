from django.urls import path

from . import views

app_name = "assignments"

urlpatterns = [
    path("<int:asset_pk>/assign/", views.assign_panel, name="assign_panel"),
    path("<int:asset_pk>/assign/clear/", views.clear_assignee, name="clear_assignee"),
    path("<int:asset_pk>/return/", views.return_panel, name="return_panel"),
    path("bulk-return/", views.bulk_return, name="bulk_return"),
    path("bulk-transfer/", views.bulk_transfer, name="bulk_transfer"),
    path("bulk-assign-clear/", views.bulk_clear_assignee, name="bulk_clear_assignee"),
    path("alerts/", views.alerts_list, name="alerts_list"),
    path("alerts/<int:pk>/", views.alert_panel, name="alert_panel"),
]
