"""Adaptateur Ollama — modèles exécutés localement, sans clé d'API."""

import httpx

from .base import DEFAULT_MAX_TOKENS, HttpBaseClient, PingResult, ProviderError


class OllamaClient(HttpBaseClient):
    def ping(self) -> PingResult:
        try:
            response = self._request("GET", "/api/tags")
        except httpx.HTTPError as exc:
            return PingResult(False, self._describe_http_error(exc))
        if response.is_error:
            return PingResult(False, self._describe_status(response))

        installed = {item["name"].split(":")[0] for item in response.json().get("models", [])}
        if self.model.split(":")[0] not in installed:
            return PingResult(
                False,
                f"Serveur joignable, mais le modèle « {self.model} » n'est pas installé. "
                f"Le télécharger : ollama pull {self.model}",
            )
        return PingResult(True, f"Serveur joignable — {self.model} disponible.")

    def generate(
        self, prompt: str, *, system: str | None = None, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> str:
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        if system:
            payload["system"] = system

        try:
            response = self._request("POST", "/api/generate", json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(self._describe_http_error(exc)) from exc
        if response.is_error:
            raise ProviderError(self._describe_status(response))

        return response.json().get("response", "")
