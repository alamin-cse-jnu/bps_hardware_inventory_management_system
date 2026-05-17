from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_index, name="index"),

    # ── View pages ─────────────────────────────────────────────────────────────
    path("view/inventory/",          views.view_inventory,            name="inventory_view"),
    path("view/holder-assignments/", views.view_holder_assignments,   name="holder_assignments_view"),
    path("view/transfer-log/",            views.view_transfer_log,         name="transfer_log_view"),
    path("view/lifecycle/",               views.view_lifecycle,            name="lifecycle_view"),
    path("view/warranty/",                views.view_warranty,             name="warranty_view"),
    path("view/asset-history/<int:pk>/",  views.view_asset_history,        name="asset_history_view"),

    # ── Excel downloads ────────────────────────────────────────────────────────
    path("excel/inventory/",           views.download_inventory,          name="inventory_excel"),
    path("excel/transfer-log/",        views.download_transfer_log,       name="transfer_log_excel"),
    path("excel/lifecycle/",           views.download_lifecycle,           name="lifecycle_excel"),
    path("excel/warranty/",            views.download_warranty,            name="warranty_excel"),
    path("excel/holder-assignments/",  views.download_holder_assignments,  name="holder_assignments_excel"),
    path("excel/asset-history/<int:pk>/", views.download_asset_history,   name="asset_history_excel"),

    # ── PDF downloads ──────────────────────────────────────────────────────────
    path("pdf/inventory/",          views.download_inventory_pdf,          name="inventory_pdf"),
    path("pdf/holder-assignments/", views.download_holder_assignments_pdf, name="holder_assignments_pdf"),
    path("pdf/transfer-log/",              views.download_transfer_log_pdf,       name="transfer_log_pdf"),
    path("pdf/lifecycle/",                 views.download_lifecycle_pdf,          name="lifecycle_pdf"),
    path("pdf/warranty/",                  views.download_warranty_pdf,           name="warranty_pdf"),
    path("pdf/asset-history/<int:pk>/",   views.download_asset_history_pdf,      name="asset_history_pdf"),
    path("pdf/handover/<int:pk>/",  views.download_handover,               name="handover_pdf"),
    path("pdf/disposal/<int:pk>/",  views.download_disposal,               name="disposal_pdf"),
]
