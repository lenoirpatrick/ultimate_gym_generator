"""Catalogue des fournisseurs d'IA générative supportés.

Ajouter un fournisseur consiste à ajouter une entrée ici et un adaptateur dans
`clients/` — rien d'autre dans l'application ne connaît la liste en dur.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSpec:
    slug: str
    name: str
    docs_url: str
    default_model: str
    default_base_url: str = ""
    requires_api_key: bool = True
    #: Aide affichée sous le champ « URL de base » quand il est pertinent.
    base_url_help: str = ""


PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        slug="anthropic",
        name="Anthropic (Claude)",
        docs_url="https://platform.claude.com/docs",
        default_model="claude-opus-5",
    ),
    ProviderSpec(
        slug="gemini",
        name="Google Gemini",
        docs_url="https://ai.google.dev/gemini-api/docs",
        default_model="gemini-2.5-pro",
        default_base_url="https://generativelanguage.googleapis.com",
    ),
    ProviderSpec(
        slug="mistral",
        name="Mistral AI",
        docs_url="https://docs.mistral.ai/",
        default_model="mistral-large-latest",
        default_base_url="https://api.mistral.ai",
    ),
    ProviderSpec(
        slug="ollama",
        name="Ollama (local)",
        docs_url="https://github.com/ollama/ollama/blob/main/docs/api.md",
        default_model="llama3.1",
        default_base_url="http://localhost:11434",
        requires_api_key=False,
        base_url_help="Adresse du serveur Ollama. Depuis un conteneur : http://host.docker.internal:11434",
    ),
)

PROVIDERS_BY_SLUG: dict[str, ProviderSpec] = {spec.slug: spec for spec in PROVIDERS}

PROVIDER_CHOICES = [(spec.slug, spec.name) for spec in PROVIDERS]


def get_spec(slug: str) -> ProviderSpec:
    """Retourne la fiche d'un fournisseur, ou lève `KeyError` s'il est inconnu."""
    return PROVIDERS_BY_SLUG[slug]
