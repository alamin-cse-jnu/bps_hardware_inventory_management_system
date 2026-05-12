from django.urls import path
from . import views

app_name = "qrcodes"

urlpatterns = [
    path("<str:asset_tag>/", views.mobile_scan, name="mobile_scan"),
    path("<int:pk>/download/", views.qr_download, name="qr_download"),
    path("<int:pk>/label/", views.qr_label, name="qr_label"),
]
