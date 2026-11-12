from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from .healthcheck import health

urlpatterns = [
    path(settings.ADMIN_PATH, admin.site.urls),
    path("healthz/", health, name="health"),
    path("api/v1/auth/", include("apps.authentication.api.urls")),
    path("api/v1/stores/", include("apps.stores.api.urls")),
    path("api/v1/", include("apps.accounts.api.urls")),
]
