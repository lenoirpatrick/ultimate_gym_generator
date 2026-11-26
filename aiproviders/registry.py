"""Catalogue des fournisseurs d'IA générative supportés.

Ajouter un fournisseur consiste à ajouter une entrée ici et un adaptateur dans
`clients/` — rien d'autre dans l'application ne connaît la liste en dur.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSpec:
    slug: str
    name: str
    default_model: str
    #: Documentation officielle du fournisseur. Vide quand il n'en a pas de
    #: publique — une passerelle locale documente son API sur sa propre adresse.
    docs_url: str = ""
    #: Page où l'utilisateur obtient sa clé d'API (ou installe le service, pour
    #: un fournisseur local). Affichée à côté du champ « clé d'API ».
    credential_url: str = ""
    #: Libellé du lien ci-dessus, adapté au fournisseur.
    credential_label: str = "Créer une clé d'API"
    #: Explication affichée à la place du lien quand le secret ne s'obtient pas
    #: sur une page web (jeton d'une passerelle installée soi-même).
    credential_help: str = ""
    #: Intitulé du champ secret : une clé d'API, ou le jeton d'une passerelle.
    credential_field_label: str = "Clé d'API"
    default_base_url: str = ""
    requires_api_key: bool = True
    #: Vrai quand le fournisseur n'a pas d'adresse publique par défaut : l'URL
    #: dépend de l'installation et doit être saisie.
    requires_base_url: bool = False
    #: Aide affichée sous le champ « URL de base » quand il est pertinent.
    base_url_help: str = ""
    #: Vrai lorsque l'adaptateur sait énumérer le catalogue du fournisseur ; le
    #: modèle se choisit alors dans un menu déroulant plutôt qu'à la saisie.
    supports_model_listing: bool = False


PROVIDERS: tuple[ProviderSpec, ...] = (
    # En tête : `get_active_client` retient le premier fournisseur configuré
    # dans l'ordre du registre.
    ProviderSpec(
        slug="claude_gateway",
        name="Claude Gateway (réseau local)",
        default_model="sonnet",
        credential_help=(
            "Le jeton est la valeur de GATEWAY_TOKEN, dans /etc/claude-gateway.env "
            "sur la machine qui héberge la passerelle. Son API est documentée à "
            "l'adresse de la passerelle, suivie de /docs."
        ),
        credential_field_label="Jeton de la passerelle",
        requires_base_url=True,
        base_url_help=(
            "Adresse de la passerelle sur le réseau local, par exemple http://192.168.1.10:8765."
        ),
        supports_model_listing=True,
    ),
    ProviderSpec(
        slug="anthropic",
        name="Anthropic (Claude)",
        docs_url="https://platform.claude.com/docs",
        credential_url="https://console.anthropic.com/settings/keys",
        default_model="claude-opus-5",
    ),
    ProviderSpec(
        slug="gemini",
        name="Google Gemini",
        docs_url="https://ai.google.dev/gemini-api/docs",
        credential_url="https://aistudio.google.com/apikey",
        default_model="gemini-2.5-pro",
        default_base_url="https://generativelanguage.googleapis.com",
        supports_model_listing=True,
    ),
    ProviderSpec(
        slug="mistral",
        name="Mistral AI",
        docs_url="https://docs.mistral.ai/",
        credential_url="https://console.mistral.ai/api-keys",
        default_model="mistral-large-latest",
        default_base_url="https://api.mistral.ai",
    ),
    ProviderSpec(
        slug="ollama",
        name="Ollama (local)",
        docs_url="https://github.com/ollama/ollama/blob/main/docs/api.md",
        # Fournisseur local : pas de clé à créer, mais un serveur à installer.
        credential_url="https://ollama.com/download",
        credential_label="Installer Ollama",
        default_model="llama3.1",
        default_base_url="http://localhost:11434",
        requires_api_key=False,
        base_url_help="Adresse du serveur Ollama.",
    ),
)

PROVIDERS_BY_SLUG: dict[str, ProviderSpec] = {spec.slug: spec for spec in PROVIDERS}

PROVIDER_CHOICES = [(spec.slug, spec.name) for spec in PROVIDERS]


def get_spec(slug: str) -> ProviderSpec:
    """Retourne la fiche d'un fournisseur, ou lève `KeyError` s'il est inconnu."""
    return PROVIDERS_BY_SLUG[slug]
