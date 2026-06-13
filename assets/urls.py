from django.urls import path

from . import catalog_views, views

app_name = "assets"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),

    # ── Catalog management (Admin only) ─────────────────────────────────────────
    path("catalog/",                       catalog_views.catalog_home,     name="catalog_home"),
    path("catalog/categories/new/",        catalog_views.category_create,  name="category_create"),
    path("catalog/categories/<int:pk>/edit/",   catalog_views.category_edit,   name="category_edit"),
    path("catalog/categories/<int:pk>/toggle/", catalog_views.category_toggle, name="category_toggle"),
    path("catalog/categories/<int:pk>/delete/", catalog_views.category_delete, name="category_delete"),
    path("catalog/types/new/",             catalog_views.type_create,      name="type_create"),
    path("catalog/types/<int:pk>/edit/",   catalog_views.type_edit,        name="type_edit"),
    path("catalog/types/<int:pk>/toggle/", catalog_views.type_toggle,      name="type_toggle"),
    path("catalog/types/<int:pk>/delete/", catalog_views.type_delete,      name="type_delete"),
    path("", views.asset_list, name="list"),
    path("new/", views.asset_create, name="create"),
    path("bulk-add/", views.asset_bulk_create, name="bulk_create"),
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
