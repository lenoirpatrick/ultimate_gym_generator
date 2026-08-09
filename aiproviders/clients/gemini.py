"""Adaptateur Google Gemini (API REST `generativelanguage`)."""

import httpx

from .base import DEFAULT_MAX_TOKENS, HttpBaseClient, PingResult, ProviderError


class GeminiClient(HttpBaseClient):
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
