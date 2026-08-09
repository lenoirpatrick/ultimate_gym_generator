"""Adaptateur Mistral AI (API REST compatible chat completions)."""

import httpx

from .base import DEFAULT_MAX_TOKENS, HttpBaseClient, PingResult, ProviderError


class MistralClient(HttpBaseClient):
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.secret}"}

    def ping(self) -> PingResult:
        try:
            response = self._request("GET", "/v1/models", headers=self._headers())
        except httpx.HTTPError as exc:
            return PingResult(False, self._describe_http_error(exc))
        if response.is_error:
            return PingResult(False, self._describe_status(response))

        available = {item["id"] for item in response.json().get("data", [])}
        if self.model not in available:
            return PingResult(
                False,
                f"Clé valide, mais le modèle « {self.model} » n'est pas disponible sur ce compte.",
            )
        return PingResult(True, f"Connexion établie — {self.model}.")

    def generate(
        self, prompt: str, *, system: str | None = None, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> str:
        messages = [{"role": "user", "content": prompt}]
        if system:
            messages.insert(0, {"role": "system", "content": system})

        try:
            response = self._request(
                "POST",
                "/v1/chat/completions",
                headers=self._headers(),
                json={"model": self.model, "messages": messages, "max_tokens": max_tokens},
            )
        except httpx.HTTPError as exc:
            raise ProviderError(self._describe_http_error(exc)) from exc
        if response.is_error:
            raise ProviderError(self._describe_status(response))

        choices = response.json().get("choices") or []
        if not choices:
            raise ProviderError("Mistral n'a retourné aucune réponse.")
        return choices[0].get("message", {}).get("content", "")
