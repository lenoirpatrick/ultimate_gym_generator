"""Table de routage racine."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("", include("core.urls")),
    path("", include("accounts.urls")),
    path("exercices/", include("exercises.urls")),
    path("seances/", include("workouts.urls")),
    path("settings/ai/", include("aiproviders.urls")),
    path(settings.ADMIN_URL, admin.site.urls),
]

if settings.OIDC_ENABLED:
    urlpatterns.append(path("oidc/", include("mozilla_django_oidc.urls")))

# Les avatars sont servis par Django. Suffisant pour une installation
# auto-hébergée à faible trafic ; derrière un reverse proxy, faire servir
# /media/ directement par le proxy et cette route devient inutile.
urlpatterns.append(
    re_path(
        rf"^{settings.MEDIA_URL.lstrip('/')}(?P<path>.*)$",
        serve,
        {"document_root": settings.MEDIA_ROOT},
    )
)
