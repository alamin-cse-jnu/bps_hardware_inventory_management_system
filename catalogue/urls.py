from django.urls import path

from . import views

app_name = "catalogue"

urlpatterns = [
    # ── Dependent dropdown JSON API ───────────────────────────────────────────
    path("sub-assets/", views.api_sub_assets, name="api_sub_assets"),
    path("brands/",     views.api_brands,     name="api_brands"),
    path("models/",     views.api_models,     name="api_models"),
    path("spec/",       views.api_spec,       name="api_spec"),

    # ── Master Data management (Admin only) ───────────────────────────────────
    path("manage/", views.manage, name="manage"),

    path("manage/main/save/",            views.main_save,   name="main_save"),
    path("manage/main/<int:pk>/toggle/", views.main_toggle, name="main_toggle"),
    path("manage/main/<int:pk>/delete/", views.main_delete, name="main_delete"),

    path("manage/sub/save/",            views.sub_save,   name="sub_save"),
    path("manage/sub/<int:pk>/toggle/", views.sub_toggle, name="sub_toggle"),
    path("manage/sub/<int:pk>/delete/", views.sub_delete, name="sub_delete"),

    path("manage/brand/save/",            views.brand_save,   name="brand_save"),
    path("manage/brand/<int:pk>/toggle/", views.brand_toggle, name="brand_toggle"),
    path("manage/brand/<int:pk>/delete/", views.brand_delete, name="brand_delete"),

    path("manage/model/save/",            views.model_save,   name="model_save"),
    path("manage/model/<int:pk>/toggle/", views.model_toggle, name="model_toggle"),
    path("manage/model/<int:pk>/delete/", views.model_delete, name="model_delete"),

    path("manage/spec-field/save/",            views.specfield_save,   name="specfield_save"),
    path("manage/spec-field/<int:pk>/toggle/", views.specfield_toggle, name="specfield_toggle"),
    path("manage/spec-field/<int:pk>/delete/", views.specfield_delete, name="specfield_delete"),
    path("manage/spec-field/<int:pk>/move/",   views.specfield_move,   name="specfield_move"),
]
