from django.urls import path

from . import views

app_name = "locations"

urlpatterns = [
    path("", views.location_list, name="list"),
    path("new/", views.location_create, name="create"),
    path("parent-options/", views.location_parent_options, name="parent_options"),
    path("<int:pk>/edit/", views.location_edit, name="edit"),
    path("<int:pk>/delete/", views.location_delete, name="delete"),
]
