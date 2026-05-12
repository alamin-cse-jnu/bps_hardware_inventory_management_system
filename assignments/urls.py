from django.urls import path
from . import views

app_name = "assignments"

urlpatterns = [
    path("<int:asset_pk>/assign/", views.assign_panel, name="assign_panel"),
    path("<int:asset_pk>/assign/clear/", views.clear_assignee, name="clear_assignee"),
    path("<int:asset_pk>/return/", views.return_panel, name="return_panel"),
]
