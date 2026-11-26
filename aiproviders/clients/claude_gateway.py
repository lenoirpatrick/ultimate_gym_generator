"""Adaptateur Claude Gateway — passerelle HTTP du réseau local devant Claude Code.

La passerelle lance `claude -p` à chaque requête : un appel dure de quelques
secondes à trois minutes, et elle n'en traite qu'un à la fois. Les deux
contraintes se lisent dans ses réponses d'erreur (504, 503), traduites ici en
messages qui disent quoi faire.
"""

import httpx

from .base import DEFAULT_MAX_TOKENS, HttpBaseClient, ModelOption, PingResult, ProviderError

#: La passerelle coupe elle-même un appel à 180 s ; la marge laisse sa propre
#: réponse 504 arriver plutôt qu'un délai dépassé côté client, moins explicite.
GENERATE_TIMEOUT = 190.0

#: `/health` et la vérification du jeton répondent sans lancer Claude Code.
PING_TIMEOUT = 10.0


class ClaudeGatewayClient(HttpBaseClient):
    # Seule la réponse peut prendre trois minutes : une passerelle éteinte doit
    # se signaler en quelques secondes, pas au bout du délai de génération.
    timeout = httpx.Timeout(GENERATE_TIMEOUT, connect=PING_TIMEOUT)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.secret}"}

    @staticmethod
    def _describe_status(response: httpx.Response) -> str:
        detail = _error_detail(response)
        status = response.status_code

        if status in (401, 403):
            return "Jeton refusé par la passerelle. Vérifie la valeur de GATEWAY_TOKEN."
        if status == 413:
            return "Requête trop volumineuse pour la passerelle (12 Mo au maximum)."
        if status == 503:
            return (
                "Passerelle occupée : elle ne traite qu'un appel à la fois. "
                "Réessaie dans quelques instants."
            )
        if status == 504:
            return (
                "La passerelle a dépassé son délai (180 s). Réessaie, "
                "ou choisis un modèle plus rapide."
            )
        if status == 502:
            return f"Claude Code a échoué sur la passerelle : {detail or 'aucun détail'}."
        if status == 400:
            return f"Requête refusée par la passerelle : {detail or 'aucun détail'}."
        return HttpBaseClient._describe_status(response)

    def ping(self) -> PingResult:
        try:
            health = self._request("GET", "/health", timeout=PING_TIMEOUT)
        except httpx.TimeoutException:
            # Sur un réseau local, une adresse sans machine derrière ne refuse
            # pas la connexion : elle ne répond simplement jamais.
            return PingResult(
                False,
                f"Passerelle injoignable : aucune réponse en {PING_TIMEOUT:.0f} s. "
                "Vérifie l'adresse et que le service tourne.",
            )
        except httpx.HTTPError as exc:
            return PingResult(False, self._describe_http_error(exc))
        if health.is_error:
            return PingResult(False, self._describe_status(health))

        # `/v1/models` est authentifiée et ne lance pas Claude Code : elle
        # vérifie le jeton sans rien consommer (issue #156).
        try:
            models = self._fetch_models()
        except ProviderError as exc:
            return PingResult(False, str(exc))

        current = next((model for model in models if model.get("id") == self.model), None)
        if current is None:
            return PingResult(
                False,
                f"Jeton valide, mais la passerelle ne propose pas le modèle « {self.model} ». "
                "Choisis-en un autre dans la configuration.",
            )

        version = _json(health).get("claude") or "Claude Code"
        resolved = f" ({current['resolved']})" if current.get("resolved") else ""
        return PingResult(True, f"Connexion établie — {version}, modèle {self.model}{resolved}.")

    def list_models(self) -> list[ModelOption]:
        """Alias acceptés par la passerelle, avec le modèle réel qu'ils désignent."""
        options = []
        for model in self._fetch_models():
            identifier = model.get("id")
            if not isinstance(identifier, str) or not identifier:
                continue
            label = f"Claude {identifier.capitalize()}"
            if model.get("resolved"):
                label = f"{label} — {model['resolved']}"
            options.append(ModelOption(identifier, label))
        return options

    def _fetch_models(self) -> list[dict]:
        try:
            response = self._request(
                "GET", "/v1/models", headers=self._headers(), timeout=PING_TIMEOUT
            )
        except httpx.HTTPError as exc:
            raise ProviderError(self._describe_http_error(exc)) from exc
        if response.status_code == 404:
            raise ProviderError(
                "Cette passerelle ne publie pas ses modèles (route /v1/models absente) : "
                "mets-la à jour."
            )
        if response.is_error:
            raise ProviderError(self._describe_status(response))

        models = _json(response).get("models")
        if not isinstance(models, list):
            raise ProviderError("La passerelle a renvoyé une liste de modèles illisible.")
        return [model for model in models if isinstance(model, dict)]

    def generate(
        self, prompt: str, *, system: str | None = None, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> str:
        """Texte produit par Claude Code.

        `max_tokens` est accepté pour respecter le contrat commun, mais la
        passerelle n'expose aucune limite de longueur : il est ignoré.
        """
        payload: dict = {"prompt": prompt, "model": self.model}
        if system:
            payload["system"] = system

        try:
            response = self._request("POST", "/v1/generate", headers=self._headers(), json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(self._describe_http_error(exc)) from exc
        if response.is_error:
            raise ProviderError(self._describe_status(response))

        text = _json(response).get("text")
        if not isinstance(text, str):
            raise ProviderError("La passerelle a répondu sans texte exploitable.")
        return text


def _json(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _error_detail(response: httpx.Response) -> str:
    """Message d'erreur de la passerelle (`{"error": "…"}`), vide s'il manque."""
    error = _json(response).get("error")
    return error.strip() if isinstance(error, str) else ""
