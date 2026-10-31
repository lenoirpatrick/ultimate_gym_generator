"""Client de l'API REST de Home Assistant.

Délai court : une instance domestique injoignable ne doit jamais faire
attendre une page de l'application, encore moins le minuteur de séance.
"""

from dataclasses import dataclass

import httpx

from .models import Connection

TIMEOUT_SECONDS = 5.0

STATE_LABELS = {
    "on": "Allumé",
    "off": "Éteint",
    "unavailable": "Indisponible",
    "unknown": "Inconnu",
}


class HomeAssistantError(Exception):
    """Échec d'appel, avec un message actionnable pour l'utilisateur."""


@dataclass(frozen=True)
class EntityState:
    """État courant d'une entité, tel qu'affiché."""

    entity_id: str
    state: str
    unit: str = ""

    @property
    def display(self) -> str:
        return f"{self.state} {self.unit}".strip()

    @property
    def label(self) -> str:
        """État lisible : « on » ne dit rien à quelqu'un qui n'a jamais ouvert
        Home Assistant. Un état sans traduction (valeur de capteur) s'affiche
        tel quel, avec son unité."""
        return STATE_LABELS.get(self.state, self.display)


class HomeAssistantClient:
    #: Transport httpx alternatif. `None` en production ; les tests y placent un
    #: `httpx.MockTransport` — même principe que `aiproviders.clients.base`.
    transport: httpx.BaseTransport | None = None

    def __init__(self, connection: Connection) -> None:
        self.base_url = connection.base_url.rstrip("/")
        self.token = connection.token

    def ping(self) -> str:
        """Vérifie adresse et jeton ; renvoie le message de succès à afficher."""
        self._request("GET", "/api/")
        return "Connexion établie."

    def state(self, entity_id: str) -> EntityState:
        payload = self._request("GET", f"/api/states/{entity_id}").json()
        attributes = payload.get("attributes") or {}
        return EntityState(
            entity_id=entity_id,
            state=str(payload.get("state", "")),
            unit=str(attributes.get("unit_of_measurement") or ""),
        )

    def call(self, entity_id: str, service: str) -> None:
        domain = entity_id.split(".", 1)[0]
        self._request("POST", f"/api/services/{domain}/{service}", json={"entity_id": entity_id})

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            with httpx.Client(timeout=TIMEOUT_SECONDS, transport=self.transport) as client:
                response = client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers={"Authorization": f"Bearer {self.token}"},
                    **kwargs,
                )
        except httpx.TimeoutException as exc:
            raise HomeAssistantError("Home Assistant ne répond pas à temps.") from exc
        except httpx.HTTPError as exc:
            raise HomeAssistantError(
                "Home Assistant est injoignable. Vérifie l'adresse et le réseau."
            ) from exc

        if response.status_code in (401, 403):
            raise HomeAssistantError("Jeton d'accès refusé par Home Assistant.")
        if response.status_code == 404:
            raise HomeAssistantError("Entité inconnue de Home Assistant.")
        if response.is_error:
            raise HomeAssistantError(
                f"Home Assistant a répondu par l'erreur {response.status_code}."
            )
        return response


def get_client() -> HomeAssistantClient | None:
    """Client prêt à l'emploi, `None` tant que la connexion n'est pas configurée."""
    connection = Connection.load()
    if connection is None or not connection.is_configured:
        return None
    return HomeAssistantClient(connection)
