"""Adaptateurs de fournisseurs : traduction des réponses et des pannes.

Aucun appel réseau réel : les adaptateurs HTTP reçoivent un `MockTransport`.
Claude Gateway a ses propres tests (`test_aiproviders_claude_gateway`).
"""

import httpx
import pytest

from aiproviders.clients import get_client
from aiproviders.clients.base import BaseClient, ProviderError
from aiproviders.models import ProviderCredential


def build(provider: str, responder, **fields):
    """Crée un adaptateur dont les requêtes HTTP sont interceptées."""
    credential = ProviderCredential(provider=provider, secret="cle-de-test", **fields)
    client = get_client(credential)
    client.transport = httpx.MockTransport(responder)
    return client


def json_response(status: int, payload: dict):
    return lambda request: httpx.Response(status, json=payload)


# --------------------------------------------------------------------------- #
# Pannes HTTP communes
# --------------------------------------------------------------------------- #


def test_un_serveur_injoignable_donne_un_message_actionnable():
    def refuse(request):
        raise httpx.ConnectError("connexion refusée", request=request)

    result = build("gemini", refuse).ping()

    assert result.ok is False
    assert "injoignable" in result.message


def test_une_cle_refusee_est_signalee_comme_telle():
    result = build("gemini", json_response(401, {"error": "unauthorized"})).ping()

    assert result.ok is False
    assert result.message == "Clé d'API refusée."


def test_un_quota_depasse_est_signale_comme_tel():
    result = build("gemini", json_response(429, {"error": "rate limited"})).ping()

    assert result.ok is False
    assert "Quota dépassé" in result.message


def test_un_delai_depasse_est_signale_comme_tel():
    def timeout(request):
        raise httpx.ReadTimeout("trop lent", request=request)

    result = build("gemini", timeout).ping()

    assert result.ok is False
    assert "Délai d'attente" in result.message


# --------------------------------------------------------------------------- #
# Gemini
# --------------------------------------------------------------------------- #


def test_gemini_confirme_un_modele_disponible():
    result = build("gemini", json_response(200, {"name": "models/gemini-2.5-pro"})).ping()

    assert result.ok is True
    assert "gemini-2.5-pro" in result.message


def test_gemini_concatene_les_fragments_de_reponse():
    payload = {"candidates": [{"content": {"parts": [{"text": "Séance "}, {"text": "push."}]}}]}

    text = build("gemini", json_response(200, payload)).generate("Programme ?")

    assert text == "Séance push."


def test_gemini_signale_une_reponse_filtree():
    with pytest.raises(ProviderError, match="aucune réponse"):
        build("gemini", json_response(200, {"candidates": []})).generate("Programme ?")


# --------------------------------------------------------------------------- #
# Gemini — catalogue des modèles (issue #7)
# --------------------------------------------------------------------------- #

CATALOGUE = {
    "models": [
        {
            "name": "models/gemini-2.5-pro",
            "displayName": "Gemini 2.5 Pro",
            "supportedGenerationMethods": ["generateContent", "countTokens"],
        },
        {
            "name": "models/text-embedding-004",
            "displayName": "Text Embedding 004",
            "supportedGenerationMethods": ["embedContent"],
        },
        {
            "name": "models/gemini-2.5-flash",
            "displayName": "Gemini 2.5 Flash",
            "supportedGenerationMethods": ["generateContent"],
        },
    ]
}


def test_gemini_ne_retient_que_les_modeles_generant_du_texte():
    """Un modèle d'embedding ne rédige pas un programme : il n'a rien à faire dans la liste."""
    models = build("gemini", json_response(200, CATALOGUE)).list_models()

    assert [model.identifier for model in models] == ["gemini-2.5-flash", "gemini-2.5-pro"]
    assert models[0].label == "Gemini 2.5 Flash"


def test_gemini_retient_un_modele_qui_n_annonce_pas_ses_methodes():
    """Mieux vaut un modèle de trop qu'une liste vide si la réponse évolue."""
    payload = {"models": [{"name": "models/gemini-3-pro", "displayName": "Gemini 3 Pro"}]}

    models = build("gemini", json_response(200, payload)).list_models()

    assert [model.identifier for model in models] == ["gemini-3-pro"]


def test_gemini_retombe_sur_l_identifiant_sans_libelle():
    payload = {"models": [{"name": "models/gemini-3-pro"}]}

    models = build("gemini", json_response(200, payload)).list_models()

    assert models[0].label == "gemini-3-pro"


def test_gemini_traduit_une_cle_refusee_lors_du_listage():
    with pytest.raises(ProviderError, match="Clé d'API refusée"):
        build("gemini", json_response(401, {"error": "unauthorized"})).list_models()


def test_gemini_reconnait_une_cle_invalide_derriere_un_400():
    """Google refuse une clé mal formée en 400, pas en 401 : le pavé JSON n'aide personne."""
    payload = {
        "error": {
            "code": 400,
            "message": "API key not valid. Please pass a valid API key.",
            "status": "INVALID_ARGUMENT",
            "details": [{"reason": "API_KEY_INVALID"}],
        }
    }

    result = build("gemini", json_response(400, payload)).ping()

    assert result.message == "Clé d'API refusée."


def test_gemini_remonte_le_message_de_google_plutot_que_le_corps_brut():
    payload = {"error": {"code": 400, "message": "Le modèle demandé n'existe plus."}}

    result = build("gemini", json_response(400, payload)).ping()

    assert result.message == "Erreur HTTP 400 : Le modèle demandé n'existe plus."


def test_gemini_traduit_un_serveur_injoignable_lors_du_listage():
    def refuse(request):
        raise httpx.ConnectError("connexion refusée", request=request)

    with pytest.raises(ProviderError, match="injoignable"):
        build("gemini", refuse).list_models()


def test_un_adaptateur_sans_catalogue_le_dit_clairement():
    """Le contrat par défaut : sans `supports_model_listing`, le modèle se saisit."""

    class SansCatalogue(BaseClient):
        def ping(self):
            raise NotImplementedError

        def generate(self, prompt, *, system=None, max_tokens=0):
            raise NotImplementedError

    with pytest.raises(ProviderError, match="ne sait pas énumérer"):
        SansCatalogue(ProviderCredential(provider="gemini", secret="cle")).list_models()


# --------------------------------------------------------------------------- #
# Fabrique
# --------------------------------------------------------------------------- #


def test_la_fabrique_refuse_un_fournisseur_inconnu():
    credential = ProviderCredential(provider="inexistant")

    with pytest.raises(ProviderError, match="non supporté"):
        get_client(credential)
