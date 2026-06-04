from django.urls import path

from . import views

app_name = "qrcodes"

urlpatterns = [
    # Audit sessions
    path("audits/", views.audit_list, name="audit_list"),
    path("audits/new/", views.audit_create, name="audit_create"),
    path("audits/<int:pk>/", views.audit_detail, name="audit_detail"),
    path("audits/<int:session_pk>/scan/<int:scan_pk>/delete/", views.audit_scan_delete, name="audit_scan_delete"),

    # QR display + download
    path("<str:asset_tag>/", views.mobile_scan, name="mobile_scan"),
    path("<int:pk>/download/", views.qr_download, name="qr_download"),
    path("<int:pk>/label/", views.qr_label, name="qr_label"),
    path("<int:pk>/spec-label/", views.spec_label, name="spec_label"),
]
