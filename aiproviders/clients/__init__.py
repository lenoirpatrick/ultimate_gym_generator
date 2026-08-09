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


__all__ = ["BaseClient", "PingResult", "ProviderError", "get_client"]
