"""Adaptateur Anthropic, via le SDK officiel `anthropic`."""

import anthropic

from .base import DEFAULT_MAX_TOKENS, DEFAULT_TIMEOUT, BaseClient, PingResult, ProviderError


class AnthropicClient(BaseClient):
    def _client(self) -> anthropic.Anthropic:
        return anthropic.Anthropic(api_key=self.secret, timeout=DEFAULT_TIMEOUT)

    def ping(self) -> PingResult:
        """Interroge l'API Models : valide la clé et le modèle sans consommer de tokens."""
        try:
            model = self._client().models.retrieve(self.model)
        except anthropic.NotFoundError:
            return PingResult(
                False,
                f"Modèle « {self.model} » introuvable. Vérifie l'identifiant du modèle.",
            )
        except anthropic.AuthenticationError:
            return PingResult(False, "Clé d'API refusée.")
        except anthropic.PermissionDeniedError:
            return PingResult(False, "Cette clé n'a pas accès à ce modèle.")
        except anthropic.RateLimitError:
            return PingResult(False, "Quota dépassé. Réessaie dans quelques instants.")
        except anthropic.APIStatusError as exc:
            return PingResult(False, f"Erreur API ({exc.status_code}) : {exc.message}")
        except anthropic.APIConnectionError:
            return PingResult(False, "Serveur injoignable. Vérifie la connexion réseau.")
        return PingResult(True, f"Connexion établie — {model.display_name}.")

    def generate(
        self, prompt: str, *, system: str | None = None, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> str:
        try:
            response = self._client().messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system or anthropic.NOT_GIVEN,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.AuthenticationError as exc:
            raise ProviderError("Clé d'API Anthropic refusée.") from exc
        except anthropic.RateLimitError as exc:
            raise ProviderError("Quota Anthropic dépassé. Réessaie plus tard.") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(
                f"Erreur API Anthropic ({exc.status_code}) : {exc.message}"
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("Anthropic injoignable. Vérifie la connexion réseau.") from exc

        # Les classificateurs de sûreté peuvent décliner une requête : la réponse
        # est un HTTP 200 dont le contenu est vide ou partiel.
        if response.stop_reason == "refusal":
            raise ProviderError(
                "Requête refusée par les filtres de sûreté du modèle. Reformule la demande."
            )

        return "".join(block.text for block in response.content if block.type == "text")
