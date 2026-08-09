"""Table de routage racine."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("core.urls")),
    path("", include("accounts.urls")),
    path("settings/ai/", include("aiproviders.urls")),
    path(settings.ADMIN_URL, admin.site.urls),
]
