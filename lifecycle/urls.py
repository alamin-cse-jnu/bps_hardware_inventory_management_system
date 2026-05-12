from django.urls import path
from . import views

app_name = "lifecycle"

urlpatterns = [
    path("<int:asset_pk>/event/", views.event_panel, name="event_panel"),
]
