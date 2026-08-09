"""Fabrique d'adaptateurs de fournisseurs d'IA."""

from .anthropic_client import AnthropicClient
from .base import BaseClient, PingResult, ProviderError
from .gemini import GeminiClient
from .mistral import MistralClient
from .ollama import OllamaClient

_CLIENTS: dict[str, type[BaseClient]] = {
    "anthropic": AnthropicClient,
    "gemini": GeminiClient,
    "mistral": MistralClient,
    "ollama": OllamaClient,
}


def get_client(credential) -> BaseClient:
    """Retourne l'adaptateur correspondant à un `ProviderCredential`."""
    try:
        return _CLIENTS[credential.provider](credential)
    except KeyError as exc:
        raise ProviderError(f"Fournisseur « {credential.provider} » non supporté.") from exc


def get_active_client() -> BaseClient | None:
    """Adaptateur du premier fournisseur utilisable, ou `None` s'il n'y en a aucun.

    L'installation peut fonctionner sans aucun fournisseur : tout appel d'IA est
    un supplément, jamais une dépendance. L'ordre est celui du registre, faute
    d'une préférence explicite — il n'y en a pas besoin tant qu'on ne configure
    qu'un fournisseur à la fois.
    """
    from aiproviders.models import ProviderCredential
    from aiproviders.registry import PROVIDERS

    configured = {
        credential.provider: credential
        for credential in ProviderCredential.objects.filter(is_active=True)
        if credential.is_configured
    }

    for spec in PROVIDERS:
        credential = configured.get(spec.slug)
        if credential is not None:
            return get_client(credential)

    return None


__all__ = ["BaseClient", "PingResult", "ProviderError", "get_active_client", "get_client"]
