"""Adaptateur Google Gemini (API REST `generativelanguage`)."""

import httpx

from .base import DEFAULT_MAX_TOKENS, HttpBaseClient, ModelOption, PingResult, ProviderError

#: Méthode que doit annoncer un modèle pour produire du texte — elle écarte les
#: modèles d'embedding et d'imagerie, sans intérêt pour un programme de séance.
TEXT_GENERATION_METHOD = "generateContent"


class GeminiClient(HttpBaseClient):
    @staticmethod
    def _describe_status(response: httpx.Response) -> str:
        """Traduit les erreurs de Google, dont le corps JSON dit mieux que le statut.

        Une clé invalide arrive en 400 `API_KEY_INVALID`, et non en 401 : sans ce
        cas particulier, l'utilisateur recevrait un extrait de JSON à déchiffrer.
        """
        if "API_KEY_INVALID" in response.text:
            return "Clé d'API refusée."

        if known := HttpBaseClient._describe_known_status(response):
            return known

        try:
            payload = response.json()
        except ValueError:
            payload = None

        error = payload.get("error") if isinstance(payload, dict) else None
        message = error.get("message", "") if isinstance(error, dict) else ""

        if message:
            return f"Erreur HTTP {response.status_code} : {message}"
        return HttpBaseClient._describe_status(response)

    def ping(self) -> PingResult:
        try:
            response = self._request(
                "GET", f"/v1beta/models/{self.model}", params={"key": self.secret}
            )
        except httpx.HTTPError as exc:
            return PingResult(False, self._describe_http_error(exc))
        if response.is_error:
            return PingResult(False, self._describe_status(response))
        return PingResult(True, f"Connexion établie — {response.json().get('name', self.model)}.")

    def list_models(self) -> list[ModelOption]:
        try:
            response = self._request(
                "GET", "/v1beta/models", params={"key": self.secret, "pageSize": 200}
            )
        except httpx.HTTPError as exc:
            raise ProviderError(self._describe_http_error(exc)) from exc
        if response.is_error:
            raise ProviderError(self._describe_status(response))

        options = []
        for entry in response.json().get("models", []):
            name = entry.get("name", "")
            methods = entry.get("supportedGenerationMethods")
            # Un catalogue qui n'annonce pas ses méthodes est retenu tel quel :
            # mieux vaut proposer un modèle de trop qu'une liste vide si Google
            # fait évoluer la forme de sa réponse.
            if not name or (methods is not None and TEXT_GENERATION_METHOD not in methods):
                continue

            identifier = name.removeprefix("models/")
            options.append(ModelOption(identifier, entry.get("displayName") or identifier))

        return sorted(options, key=lambda option: option.label)

    def generate(
        self, prompt: str, *, system: str | None = None, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> str:
        payload: dict = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        try:
            response = self._request(
                "POST",
                f"/v1beta/models/{self.model}:generateContent",
                params={"key": self.secret},
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(self._describe_http_error(exc)) from exc
        if response.is_error:
            raise ProviderError(self._describe_status(response))

        candidates = response.json().get("candidates") or []
        if not candidates:
            raise ProviderError("Gemini n'a retourné aucune réponse (contenu probablement filtré).")
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(part.get("text", "") for part in parts)
