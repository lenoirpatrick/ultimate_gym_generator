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


@dataclass(frozen=True)
class ModelOption:
    """Modèle proposé par un fournisseur, tel qu'affiché dans un menu déroulant."""

    #: Identifiant technique, celui qui part dans les appels.
    identifier: str
    #: Libellé lisible, celui que voit l'utilisateur.
    label: str


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

    def list_models(self) -> list[ModelOption]:
        """Modèles de génération de texte accessibles avec ces credentials.

        Tous les fournisseurs ne savent pas énumérer leur catalogue ; le modèle
        se saisit alors à la main. `ProviderSpec.supports_model_listing` indique
        lesquels répondent à cet appel.
        """
        raise ProviderError(
            f"{type(self).__name__} ne sait pas énumérer les modèles de ce fournisseur."
        )


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
    def _describe_known_status(response: httpx.Response) -> str | None:
        """Message des statuts que tous les fournisseurs partagent, `None` sinon.

        Isolé du repli pour qu'un adaptateur puisse enrichir les autres statuts
        sans réécrire ces traductions ni les faire diverger.
        """
        if response.status_code in (401, 403):
            return "Clé d'API refusée."
        if response.status_code == 404:
            return "Ressource introuvable. Vérifie l'URL de base et le modèle."
        if response.status_code == 429:
            return "Quota dépassé. Réessaie dans quelques instants."
        return None

    @staticmethod
    def _describe_status(response: httpx.Response) -> str:
        known = HttpBaseClient._describe_known_status(response)
        return known or f"Erreur HTTP {response.status_code} : {response.text[:200]}"
