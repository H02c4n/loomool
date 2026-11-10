from django.conf import settings
from django.contrib import admin
from django.urls import path

from .healthcheck import health

urlpatterns = [
    path(settings.ADMIN_PATH, admin.site.urls),
    path("healthz/", health, name="health"),
]
