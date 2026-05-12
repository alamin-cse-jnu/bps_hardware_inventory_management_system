from django.urls import path
from . import views

app_name = "assignees"

urlpatterns = [
    path("search/", views.search, name="search"),
    path("<int:pk>/select/", views.select_card, name="select"),
]
