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
    # Dropdown option management
    path("catalog/dropdowns/",                              catalog_views.dropdowns_home,       name="dropdowns_home"),
    path("catalog/brands/new/",                             catalog_views.brand_create,         name="brand_create"),
    path("catalog/brands/<int:pk>/edit/",                   catalog_views.brand_edit,           name="brand_edit"),
    path("catalog/brands/<int:pk>/toggle/",                 catalog_views.brand_toggle,         name="brand_toggle"),
    path("catalog/brands/<int:pk>/delete/",                 catalog_views.brand_delete,         name="brand_delete"),
    path("catalog/model-names/new/",                        catalog_views.model_name_create,    name="model_name_create"),
    path("catalog/model-names/<int:pk>/edit/",              catalog_views.model_name_edit,      name="model_name_edit"),
    path("catalog/model-names/<int:pk>/toggle/",            catalog_views.model_name_toggle,    name="model_name_toggle"),
    path("catalog/model-names/<int:pk>/delete/",            catalog_views.model_name_delete,    name="model_name_delete"),
    path("catalog/vendors/new/",                            catalog_views.vendor_create,        name="vendor_create"),
    path("catalog/vendors/<int:pk>/edit/",                  catalog_views.vendor_edit,          name="vendor_edit"),
    path("catalog/vendors/<int:pk>/toggle/",                catalog_views.vendor_toggle,        name="vendor_toggle"),
    path("catalog/vendors/<int:pk>/delete/",                catalog_views.vendor_delete,        name="vendor_delete"),
    path("catalog/spec-choices/",                           catalog_views.spec_choices_home,    name="spec_choices_home"),
    path("catalog/spec-choices/new/",                       catalog_views.spec_choice_create,   name="spec_choice_create"),
    path("catalog/spec-choices/<int:pk>/edit/",             catalog_views.spec_choice_edit,     name="spec_choice_edit"),
    path("catalog/spec-choices/<int:pk>/toggle/",           catalog_views.spec_choice_toggle,   name="spec_choice_toggle"),
    path("catalog/spec-choices/<int:pk>/delete/",           catalog_views.spec_choice_delete,   name="spec_choice_delete"),
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
    path("work-orders/<int:pk>/view/", views.work_order_serve, name="work_order_serve"),
]
