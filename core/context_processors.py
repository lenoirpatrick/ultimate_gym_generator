"""Variables de gabarit disponibles partout."""

from django.conf import settings
from django.http import HttpRequest


def site(request: HttpRequest) -> dict[str, object]:
    return {
        "site_name": "Ultimate Gym Generator",
        "debug": settings.DEBUG,
        # Options d'authentification, pour n'afficher que ce qui est réellement
        # disponible sur cette installation.
        "sso_enabled": settings.OIDC_ENABLED,
        "sso_provider_name": settings.OIDC_PROVIDER_NAME,
        "self_registration_enabled": settings.ALLOW_SELF_REGISTRATION,
    }
