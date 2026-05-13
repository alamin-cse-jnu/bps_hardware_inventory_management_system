from django.urls import path
from . import views

app_name = "assignees"

urlpatterns = [
    # Used by assignment panel (Session 2.2)
    path("search/", views.search, name="search"),
    path("<int:pk>/select/", views.select_card, name="select"),

    # Employees
    path("employees/", views.employee_list, name="employees"),
    path("employees/new/", views.employee_create, name="employee_create"),
    path("employees/<int:pk>/", views.employee_detail, name="employee_detail"),
    path("employees/<int:pk>/edit/", views.employee_edit, name="employee_edit"),
    path("employees/<int:pk>/deactivate/", views.employee_deactivate, name="employee_deactivate"),

    # MPs
    path("mps/", views.mp_list, name="mps"),
    path("mps/new/", views.mp_create, name="mp_create"),
    path("mps/<int:pk>/", views.mp_detail, name="mp_detail"),
    path("mps/<int:pk>/edit/", views.mp_edit, name="mp_edit"),
    path("mps/<int:pk>/deactivate/", views.mp_deactivate, name="mp_deactivate"),

    # Offices
    path("offices/", views.office_list, name="offices"),
    path("offices/new/", views.office_create, name="office_create"),
    path("offices/<int:pk>/", views.office_detail, name="office_detail"),
    path("offices/<int:pk>/edit/", views.office_edit, name="office_edit"),
    path("offices/<int:pk>/deactivate/", views.office_deactivate, name="office_deactivate"),
]
