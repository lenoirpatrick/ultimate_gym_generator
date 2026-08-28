"""Authentification de l'API d'ingestion (#71) par clé API, hors session.

L'API reçoit des envois d'un raccourci iOS ou d'une application tierce, sans
cookie de session ni jeton CSRF : la clé, envoyée dans l'en-tête `Authorization`,
tient lieu d'identité. Le préfixe (non secret) sert uniquement à retrouver la
ligne candidate ; la comparaison du secret se fait par `check_password`, jamais
en clair.
"""

from django.http import HttpRequest
from django.utils import timezone

from .models import ApiKey

PREFIX_LENGTH = 8


def authenticate_request(request: HttpRequest):
    """Utilisateur propriétaire de la clé API portée par la requête, ou `None`."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None

    raw_key = header.removeprefix("Bearer ").strip()
    if len(raw_key) <= PREFIX_LENGTH:
        return None

    prefix = raw_key[:PREFIX_LENGTH]
    try:
        api_key = ApiKey.objects.select_related("user").get(prefix=prefix)
    except ApiKey.DoesNotExist:
        return None

    if not api_key.matches(raw_key):
        return None

    ApiKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())
    return api_key.user
