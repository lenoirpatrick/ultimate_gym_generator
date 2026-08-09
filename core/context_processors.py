"""Variables de gabarit disponibles partout."""

from django.conf import settings
from django.http import HttpRequest


def site(request: HttpRequest) -> dict[str, object]:
    return {
        "site_name": "Ultimate Gym Generator",
        "debug": settings.DEBUG,
    }
