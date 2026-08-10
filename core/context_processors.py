"""Variables de gabarit disponibles partout."""

from django.conf import settings
from django.http import HttpRequest

from . import nav


def site(request: HttpRequest) -> dict[str, object]:
    user = getattr(request, "user", None)
    resolved = getattr(request, "resolver_match", None)

    return {
        "site_name": "Ultimate Gym Generator",
        "debug": settings.DEBUG,
        # Options d'authentification, pour n'afficher que ce qui est réellement
        # disponible sur cette installation.
        "sso_enabled": settings.OIDC_ENABLED,
        "sso_provider_name": settings.OIDC_PROVIDER_NAME,
        "self_registration_enabled": settings.ALLOW_SELF_REGISTRATION,
        # Menu principal : une seule description, rendue en barre et dans le
        # tiroir. Voir core/nav.py.
        "primary_nav": nav.PRIMARY,
        "config_nav": nav.config_groups(user),
        # Nom de la vue courante, pour marquer l'entrée active (`aria-current`).
        "current_view": resolved.view_name if resolved else "",
    }
