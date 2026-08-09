"""Contrat commun à tous les adaptateurs de fournisseurs d'IA."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

DEFAULT_MAX_TOKENS = 16_000
DEFAULT_TIMEOUT = 30.0


@dataclass(frozen=True)
class PingResult:
    """Issue d'un test de connexion, destinée à être affichée telle quelle."""

    ok: bool
    message: str


class ProviderError(Exception):
    """Échec d'appel à un fournisseur, avec un message actionnable pour l'utilisateur."""


class BaseClient(ABC):
    """Adaptateur d'un fournisseur.

    `ping()` vérifie les credentials sans consommer de tokens ; `generate()`
    produit du texte. Les deux traduisent les erreurs du fournisseur en
    `ProviderError` porteuse d'un message exploitable — jamais une trace brute.
    """

    def __init__(self, credential) -> None:
        self.credential = credential
        self.secret = credential.secret
        self.base_url = credential.effective_base_url
        self.model = credential.effective_model

    @abstractmethod
    def ping(self) -> PingResult:
        """Vérifie que les credentials permettent de joindre le fournisseur."""

    @abstractmethod
    def generate(
        self, prompt: str, *, system: str | None = None, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> str:
        """Retourne le texte produit par le modèle."""


class HttpBaseClient(BaseClient):
    """Base des adaptateurs appelant une API REST via httpx.

    Anthropic fait exception : son SDK officiel est utilisé à la place.
    """

    #: Transport httpx alternatif. `None` en production ; les tests y placent un
    #: `httpx.MockTransport` pour exercer les adaptateurs sans accès réseau.
    transport: httpx.BaseTransport | None = None

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self.base_url.rstrip('/')}{path}"
        with httpx.Client(timeout=DEFAULT_TIMEOUT, transport=self.transport) as client:
            return client.request(method, url, **kwargs)

    @staticmethod
    def _describe_http_error(exc: httpx.HTTPError) -> str:
        if isinstance(exc, httpx.TimeoutException):
            return "Délai d'attente dépassé."
        if isinstance(exc, httpx.ConnectError):
            return "Serveur injoignable. Vérifie l'URL de base et le réseau."
        return f"Erreur réseau : {exc}"

    @staticmethod
    def _describe_status(response: httpx.Response) -> str:
        if response.status_code in (401, 403):
            return "Clé d'API refusée."
        if response.status_code == 404:
            return "Ressource introuvable. Vérifie l'URL de base et le modèle."
        if response.status_code == 429:
            return "Quota dépassé. Réessaie dans quelques instants."
        return f"Erreur HTTP {response.status_code} : {response.text[:200]}"
