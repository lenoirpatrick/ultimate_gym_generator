"""Adaptateurs de fournisseurs : traduction des réponses et des pannes.

Aucun appel réseau réel : les adaptateurs HTTP reçoivent un `MockTransport`,
et l'adaptateur Anthropic un client SDK factice.
"""

import anthropic
import httpx
import pytest

from aiproviders.clients import get_client
from aiproviders.clients.base import ProviderError
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
# Pannes communes aux adaptateurs HTTP
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("provider", ["gemini", "mistral", "ollama"])
def test_un_serveur_injoignable_donne_un_message_actionnable(provider):
    def refuse(request):
        raise httpx.ConnectError("connexion refusée", request=request)

    result = build(provider, refuse).ping()

    assert result.ok is False
    assert "injoignable" in result.message


@pytest.mark.parametrize("provider", ["gemini", "mistral"])
def test_une_cle_refusee_est_signalee_comme_telle(provider):
    result = build(provider, json_response(401, {"error": "unauthorized"})).ping()

    assert result.ok is False
    assert result.message == "Clé d'API refusée."


@pytest.mark.parametrize("provider", ["gemini", "mistral", "ollama"])
def test_un_quota_depasse_est_signale_comme_tel(provider):
    result = build(provider, json_response(429, {"error": "rate limited"})).ping()

    assert result.ok is False
    assert "Quota dépassé" in result.message


@pytest.mark.parametrize("provider", ["gemini", "mistral", "ollama"])
def test_un_delai_depasse_est_signale_comme_tel(provider):
    def timeout(request):
        raise httpx.ReadTimeout("trop lent", request=request)

    result = build(provider, timeout).ping()

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
# Mistral
# --------------------------------------------------------------------------- #


def test_mistral_confirme_un_modele_disponible():
    payload = {"data": [{"id": "mistral-large-latest"}]}

    result = build("mistral", json_response(200, payload)).ping()

    assert result.ok is True


def test_mistral_signale_un_modele_absent_du_compte():
    payload = {"data": [{"id": "mistral-small-latest"}]}

    result = build("mistral", json_response(200, payload)).ping()

    assert result.ok is False
    assert "n'est pas disponible" in result.message


def test_mistral_retourne_le_contenu_du_premier_choix():
    payload = {"choices": [{"message": {"content": "3 séries de 8."}}]}

    text = build("mistral", json_response(200, payload)).generate("Combien de séries ?")

    assert text == "3 séries de 8."


def test_mistral_transmet_le_jeton_en_bearer():
    captured = {}

    def capture(request):
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(200, json={"data": [{"id": "mistral-large-latest"}]})

    build("mistral", capture).ping()

    assert captured["authorization"] == "Bearer cle-de-test"


# --------------------------------------------------------------------------- #
# Ollama
# --------------------------------------------------------------------------- #


def test_ollama_confirme_un_modele_installe():
    payload = {"models": [{"name": "llama3.1:latest"}]}

    result = build("ollama", json_response(200, payload)).ping()

    assert result.ok is True


def test_ollama_indique_la_commande_de_telechargement_si_le_modele_manque():
    result = build("ollama", json_response(200, {"models": []})).ping()

    assert result.ok is False
    assert "ollama pull llama3.1" in result.message


def test_ollama_retourne_la_reponse_generee():
    text = build("ollama", json_response(200, {"response": "Échauffement 10 min."})).generate("Go")

    assert text == "Échauffement 10 min."


# --------------------------------------------------------------------------- #
# Anthropic — SDK officiel, remplacé par un double
# --------------------------------------------------------------------------- #


class _FakeModels:
    def __init__(self, outcome):
        self._outcome = outcome

    def retrieve(self, model_id):
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


class _FakeSdk:
    def __init__(self, models=None, messages=None):
        self.models = _FakeModels(models)
        self.messages = messages


def anthropic_client(monkeypatch, sdk):
    credential = ProviderCredential(provider="anthropic", secret="sk-ant-test")
    client = get_client(credential)
    monkeypatch.setattr(client, "_client", lambda: sdk)
    return client


def api_error(cls, status: int):
    """Construit une erreur du SDK sans passer par un vrai échange HTTP."""
    request = httpx.Request("GET", "https://api.anthropic.com/v1/models")
    return cls("refusé", response=httpx.Response(status, request=request), body=None)


def test_anthropic_confirme_le_modele(monkeypatch):
    model = type("Model", (), {"display_name": "Claude Opus 5"})()

    result = anthropic_client(monkeypatch, _FakeSdk(models=model)).ping()

    assert result.ok is True
    assert "Claude Opus 5" in result.message


def test_anthropic_signale_un_modele_inconnu(monkeypatch):
    sdk = _FakeSdk(models=api_error(anthropic.NotFoundError, 404))

    result = anthropic_client(monkeypatch, sdk).ping()

    assert result.ok is False
    assert "introuvable" in result.message


def test_anthropic_signale_une_cle_refusee(monkeypatch):
    sdk = _FakeSdk(models=api_error(anthropic.AuthenticationError, 401))

    result = anthropic_client(monkeypatch, sdk).ping()

    assert result.ok is False
    assert result.message == "Clé d'API refusée."


def test_anthropic_signale_un_serveur_injoignable(monkeypatch):
    request = httpx.Request("GET", "https://api.anthropic.com/v1/models")
    sdk = _FakeSdk(models=anthropic.APIConnectionError(request=request))

    result = anthropic_client(monkeypatch, sdk).ping()

    assert result.ok is False
    assert "injoignable" in result.message


def test_anthropic_concatene_les_blocs_texte(monkeypatch):
    block = type("Block", (), {"type": "text", "text": "Squat 5x5."})()
    response = type("Response", (), {"stop_reason": "end_turn", "content": [block]})()
    messages = type("Messages", (), {"create": lambda self, **kwargs: response})()

    text = anthropic_client(monkeypatch, _FakeSdk(messages=messages)).generate("Programme ?")

    assert text == "Squat 5x5."


def test_anthropic_signale_un_refus_des_filtres_de_surete(monkeypatch):
    response = type("Response", (), {"stop_reason": "refusal", "content": []})()
    messages = type("Messages", (), {"create": lambda self, **kwargs: response})()

    with pytest.raises(ProviderError, match="filtres de sûreté"):
        anthropic_client(monkeypatch, _FakeSdk(messages=messages)).generate("…")


# --------------------------------------------------------------------------- #
# Fabrique
# --------------------------------------------------------------------------- #


def test_la_fabrique_refuse_un_fournisseur_inconnu():
    credential = ProviderCredential(provider="inexistant")

    with pytest.raises(ProviderError, match="non supporté"):
        get_client(credential)
