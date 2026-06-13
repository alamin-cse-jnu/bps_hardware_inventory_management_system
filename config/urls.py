from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from django.views.generic import RedirectView

from django.views.defaults import permission_denied
from config import views as config_views

handler403 = "django.views.defaults.permission_denied"

admin.site.site_header = "IT Inventory Admin"
admin.site.site_title = "Parliament IT Inventory"
admin.site.index_title = "IT Assets Management"

_user_patterns = ([
    path("", config_views.user_list, name="user_list"),
    path("new/", config_views.user_create, name="user_create"),
    path("<int:pk>/edit/", config_views.user_edit, name="user_edit"),
    path("<int:pk>/toggle/", config_views.user_toggle_active, name="user_toggle_active"),
], "config")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("api/", include("rest_framework.urls")),
    path("sync/", include("sync_prp.urls", namespace="sync_prp")),
    path("locations/", include("locations.urls", namespace="locations")),
    path("", include("assets.urls", namespace="assets")),
    path("assignees/", include("assignees.urls", namespace="assignees")),
    path("assignments/", include("assignments.urls", namespace="assignments")),
    path("lifecycle/", include("lifecycle.urls", namespace="lifecycle")),
    path("qr/", include("qrcodes.urls", namespace="qrcodes")),
    path("reports/", include("reports.urls", namespace="reports")),
    path("activity/", include("audit.urls", namespace="audit")),
    path("users/", include(_user_patterns)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
