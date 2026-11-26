"""Adaptateur Claude Gateway (issue #150) : appels, test de connexion, pannes.

Aucun appel réseau réel : les requêtes passent par un `httpx.MockTransport`.
"""

import json

import httpx
import pytest
from django.urls import reverse

from aiproviders.clients import get_client
from aiproviders.clients.base import ProviderError
from aiproviders.clients.claude_gateway import GENERATE_TIMEOUT, ClaudeGatewayClient
from aiproviders.forms import ProviderCredentialForm
from aiproviders.models import ProviderCredential
from aiproviders.registry import get_spec

BASE_URL = "http://passerelle.test:8765"
TOKEN = "jeton-de-test"


def build(responder, **fields) -> ClaudeGatewayClient:
    fields.setdefault("base_url", BASE_URL)
    credential = ProviderCredential(provider="claude_gateway", secret=TOKEN, **fields)
    client = get_client(credential)
    client.transport = httpx.MockTransport(responder)
    return client


def gateway(*, health=200, generate=(200, {"text": "Réponse."}), seen=None):
    """Simule la passerelle : `/health` puis `/v1/generate`, en notant les requêtes reçues."""

    def respond(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if request.url.path == "/health":
            return httpx.Response(health, json={"status": "ok", "claude": "2.1.311 (Claude Code)"})
        status, payload = generate
        return httpx.Response(status, json=payload)

    return respond


# --------------------------------------------------------------------------- #
# Génération
# --------------------------------------------------------------------------- #


def test_generate_envoie_prompt_systeme_et_modele_avec_le_jeton():
    seen: list[httpx.Request] = []

    text = build(gateway(seen=seen), default_model="haiku").generate(
        "Programme ?", system="Tu es coach."
    )

    assert text == "Réponse."
    request = seen[0]
    assert request.url == f"{BASE_URL}/v1/generate"
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    assert json.loads(request.content) == {
        "prompt": "Programme ?",
        "system": "Tu es coach.",
        "model": "haiku",
    }


def test_generate_sans_systeme_ne_l_envoie_pas():
    seen: list[httpx.Request] = []

    build(gateway(seen=seen)).generate("Programme ?")

    assert json.loads(seen[0].content) == {"prompt": "Programme ?", "model": "sonnet"}


def test_le_delai_d_attente_couvre_la_duree_maximale_d_un_appel():
    """La passerelle accorde 180 s à Claude Code : 30 s couperaient un appel normal."""
    assert ClaudeGatewayClient.timeout == GENERATE_TIMEOUT
    assert GENERATE_TIMEOUT > 180


def test_une_reponse_sans_texte_est_une_erreur():
    with pytest.raises(ProviderError, match="sans texte"):
        build(gateway(generate=(200, {"model": "sonnet"}))).generate("Programme ?")


@pytest.mark.parametrize(
    ("status", "attendu"),
    [
        (400, "Requête refusée par la passerelle : prompt manquant"),
        (401, "Jeton refusé"),
        (413, "12 Mo"),
        (502, "Claude Code a échoué sur la passerelle : prompt manquant"),
        (503, "qu'un appel à la fois"),
        (504, "délai (180 s)"),
    ],
)
def test_chaque_code_d_erreur_donne_un_message_actionnable(status, attendu):
    responder = gateway(generate=(status, {"error": "prompt manquant"}))

    with pytest.raises(ProviderError, match=attendu.replace("(", r"\(").replace(")", r"\)")):
        build(responder).generate("Programme ?")


def test_un_delai_depasse_cote_client_est_signale():
    def lent(request):
        raise httpx.ReadTimeout("trop lent", request=request)

    with pytest.raises(ProviderError, match="Délai d'attente"):
        build(lent).generate("Programme ?")


def test_une_passerelle_injoignable_est_signalee():
    def refuse(request):
        raise httpx.ConnectError("connexion refusée", request=request)

    with pytest.raises(ProviderError, match="injoignable"):
        build(refuse).generate("Programme ?")


# --------------------------------------------------------------------------- #
# Test de connexion
# --------------------------------------------------------------------------- #


def test_le_ping_valide_le_jeton_sans_lancer_claude_code():
    """Un corps vide est refusé en 400 après le jeton : rien n'est consommé."""
    seen: list[httpx.Request] = []

    result = build(gateway(generate=(400, {"error": "prompt manquant"}), seen=seen)).ping()

    assert result.ok is True
    assert "2.1.311" in result.message
    assert [request.url.path for request in seen] == ["/health", "/v1/generate"]
    assert json.loads(seen[1].content) == {}


def test_le_ping_distingue_un_jeton_refuse():
    result = build(gateway(generate=(401, {"error": "jeton invalide"}))).ping()

    assert result.ok is False
    assert "Jeton refusé" in result.message


def test_le_ping_distingue_une_passerelle_injoignable():
    def refuse(request):
        raise httpx.ConnectError("connexion refusée", request=request)

    result = build(refuse).ping()

    assert result.ok is False
    assert "injoignable" in result.message


def test_le_ping_signale_une_passerelle_en_erreur():
    result = build(gateway(health=500)).ping()

    assert result.ok is False
    assert "500" in result.message


# --------------------------------------------------------------------------- #
# Modèles et configuration
# --------------------------------------------------------------------------- #


def test_les_modeles_proposes_sont_ceux_de_la_passerelle():
    def interdit(request):
        raise AssertionError("la liste des modèles ne doit pas appeler la passerelle")

    models = build(interdit).list_models()

    assert [model.identifier for model in models] == ["haiku", "sonnet", "opus"]


@pytest.mark.django_db
def test_sans_url_la_passerelle_n_est_pas_configuree():
    credential = ProviderCredential.objects.create(provider="claude_gateway", secret=TOKEN)

    assert credential.is_configured is False


@pytest.mark.django_db
def test_sans_jeton_la_passerelle_n_est_pas_configuree():
    credential = ProviderCredential.objects.create(provider="claude_gateway", base_url=BASE_URL)

    assert credential.is_configured is False


@pytest.mark.django_db
def test_url_et_jeton_suffisent_a_configurer_la_passerelle():
    credential = ProviderCredential.objects.create(
        provider="claude_gateway", secret=TOKEN, base_url=BASE_URL
    )

    assert credential.is_configured is True
    assert credential.effective_model == "sonnet"


@pytest.mark.django_db
def test_le_formulaire_exige_l_url_de_la_passerelle():
    form = ProviderCredentialForm(
        {"secret": TOKEN, "base_url": "", "default_model": "", "is_active": "on"},
        spec=get_spec("claude_gateway"),
    )

    assert not form.is_valid()
    assert "base_url" in form.errors


@pytest.mark.django_db
def test_le_formulaire_parle_de_jeton_et_explique_ou_le_trouver(staff_client):
    content = staff_client.get(reverse("aiproviders:edit", args=["claude_gateway"])).content
    content = content.decode()

    assert "Jeton de la passerelle" in content
    assert "GATEWAY_TOKEN" in content


@pytest.mark.django_db
def test_la_configuration_s_enregistre_depuis_l_ecran(staff_client):
    response = staff_client.post(
        reverse("aiproviders:edit", args=["claude_gateway"]),
        {"secret": TOKEN, "base_url": BASE_URL, "default_model": "opus", "is_active": "on"},
    )

    assert response.status_code == 302
    credential = ProviderCredential.objects.get(provider="claude_gateway")
    assert credential.secret == TOKEN
    assert credential.effective_model == "opus"


def test_le_ping_d_une_adresse_muette_parle_de_passerelle_injoignable():
    """Sur un réseau local, une adresse sans machine ne refuse pas : elle se tait."""

    def muet(request):
        raise httpx.ConnectTimeout("aucune réponse", request=request)

    result = build(muet).ping()

    assert result.ok is False
    assert "Passerelle injoignable" in result.message
