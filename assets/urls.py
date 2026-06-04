from django.urls import path

from . import views

app_name = "assets"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("", views.asset_list, name="list"),
    path("new/", views.asset_create, name="create"),
    path("import/", views.import_upload, name="import_upload"),
    path("import/confirm/", views.import_confirm, name="import_confirm"),
    path("import/template/", views.import_template, name="import_template"),
    path("spec-fields/", views.asset_spec_fields, name="spec_fields"),
    path("tag-check/", views.asset_tag_check, name="tag_check"),
    path("search/", views.global_search, name="global_search"),
    path("register/print/", views.asset_register_print, name="register_print"),
    path("<int:pk>/", views.asset_detail, name="detail"),
    path("<int:pk>/edit/", views.asset_edit, name="edit"),
    path("<int:pk>/delete/", views.asset_delete, name="delete"),
    path("<int:pk>/history/print/", views.asset_history_print, name="history_print"),
]
