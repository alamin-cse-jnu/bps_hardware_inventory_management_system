from django.urls import path
from . import views

app_name = "assignees"

urlpatterns = [
    # Used by assignment panel (Session 2.2)
    path("search/", views.search, name="search"),
    path("<int:pk>/select/", views.select_card, name="select"),

    # Active holders overview
    path("active/", views.active_holders, name="active_holders"),

    # Employees
    path("employees/", views.employee_list, name="employees"),
    path("employees/new/", views.employee_create, name="employee_create"),
    path("employees/<int:pk>/", views.employee_detail, name="employee_detail"),
    path("employees/<int:pk>/edit/", views.employee_edit, name="employee_edit"),
    path("employees/<int:pk>/deactivate/", views.employee_deactivate, name="employee_deactivate"),
    path("employees/<int:pk>/history/print/", views.employee_history_print, name="employee_history_print"),

    # MPs
    path("mps/", views.mp_list, name="mps"),
    path("mps/new/", views.mp_create, name="mp_create"),
    path("mps/<int:pk>/", views.mp_detail, name="mp_detail"),
    path("mps/<int:pk>/edit/", views.mp_edit, name="mp_edit"),
    path("mps/<int:pk>/deactivate/", views.mp_deactivate, name="mp_deactivate"),
    path("mps/<int:pk>/history/print/", views.mp_history_print, name="mp_history_print"),

    # Offices
    path("offices/", views.office_list, name="offices"),
    path("offices/new/", views.office_create, name="office_create"),
    path("offices/<int:pk>/", views.office_detail, name="office_detail"),
    path("offices/<int:pk>/edit/", views.office_edit, name="office_edit"),
    path("offices/<int:pk>/deactivate/", views.office_deactivate, name="office_deactivate"),
    path("offices/<int:pk>/history/print/", views.office_history_print, name="office_history_print"),
]
