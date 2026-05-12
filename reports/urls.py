from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_index, name="index"),

    # Excel
    path("excel/inventory/", views.download_inventory, name="inventory_excel"),
    path("excel/transfer-log/", views.download_transfer_log, name="transfer_log_excel"),
    path("excel/lifecycle/", views.download_lifecycle, name="lifecycle_excel"),
    path("excel/warranty/", views.download_warranty, name="warranty_excel"),
    path("excel/asset-history/<int:pk>/", views.download_asset_history, name="asset_history_excel"),

    # PDF
    path("pdf/handover/<int:pk>/", views.download_handover, name="handover_pdf"),
    path("pdf/disposal/<int:pk>/", views.download_disposal, name="disposal_pdf"),
]
