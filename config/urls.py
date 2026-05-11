from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

admin.site.site_header = "IT Inventory Admin"
admin.site.site_title = "Parliament IT Inventory"
admin.site.index_title = "IT Assets Management"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("api/", include("rest_framework.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
