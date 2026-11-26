"""Adaptateur Claude Gateway (issue #150) : appels, test de connexion, pannes.

Aucun appel réseau réel : les requêtes passent par un `httpx.MockTransport`.
"""

import json

import httpx
import pytest
from django.urls import reverse

from aiproviders.clients import get_client
from aiproviders.clients.base import ModelOption, ProviderError
from aiproviders.clients.claude_gateway import (
    GENERATE_TIMEOUT,
    PING_TIMEOUT,
    ClaudeGatewayClient,
)
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


#: Réponse de `/v1/models`, telle que la passerelle la renvoie (issue #156).
MODELS_PAYLOAD = {
    "default": "sonnet",
    "models": [
        {"id": "haiku", "description": "Le plus rapide.", "resolved": "claude-haiku-5-5"},
        {"id": "sonnet", "description": "Équilibré.", "default": True, "resolved": None},
        {"id": "opus", "description": "Le plus capable.", "resolved": "claude-opus-5-5"},
    ],
}


def gateway(
    *, health=200, generate=(200, {"text": "Réponse."}), models=(200, MODELS_PAYLOAD), seen=None
):
    """Simule la passerelle (`/health`, `/v1/models`, `/v1/generate`), en notant les requêtes."""

    def respond(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if request.url.path == "/health":
            return httpx.Response(health, json={"status": "ok", "claude": "2.1.311 (Claude Code)"})
        status, payload = models if request.url.path == "/v1/models" else generate
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
    assert ClaudeGatewayClient.timeout.read == GENERATE_TIMEOUT
    assert GENERATE_TIMEOUT > 180


def test_une_passerelle_eteinte_se_signale_sans_attendre_le_delai_de_generation():
    """Sans quoi chaque fiche d'une traduction en masse attendrait trois minutes."""
    assert ClaudeGatewayClient.timeout.connect == PING_TIMEOUT
    assert PING_TIMEOUT < 30


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


def test_le_ping_valide_le_jeton_par_la_liste_des_modeles():
    """`/v1/models` est authentifiée et ne lance pas Claude Code : rien n'est consommé."""
    seen: list[httpx.Request] = []

    result = build(gateway(seen=seen), default_model="opus").ping()

    assert result.ok is True
    assert "2.1.311" in result.message
    assert "opus (claude-opus-5-5)" in result.message
    assert [request.url.path for request in seen] == ["/health", "/v1/models"]
    assert seen[1].headers["authorization"] == f"Bearer {TOKEN}"


def test_le_ping_signale_un_modele_que_la_passerelle_ne_propose_plus():
    payload = {"models": [{"id": "haiku"}]}

    result = build(gateway(models=(200, payload)), default_model="opus").ping()

    assert result.ok is False
    assert "ne propose pas le modèle « opus »" in result.message


def test_le_ping_d_une_passerelle_sans_route_des_modeles_invite_a_la_mettre_a_jour():
    result = build(gateway(models=(404, {"error": "introuvable"}))).ping()

    assert result.ok is False
    assert "mets-la à jour" in result.message


def test_le_ping_distingue_un_jeton_refuse():
    result = build(gateway(models=(401, {"error": "jeton invalide"}))).ping()

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


def test_les_modeles_proposes_sont_lus_sur_la_passerelle():
    seen: list[httpx.Request] = []

    models = build(gateway(seen=seen)).list_models()

    assert [model.identifier for model in models] == ["haiku", "sonnet", "opus"]
    assert models[0].label == "Claude Haiku — claude-haiku-5-5"
    # `resolved` à null tant que la passerelle n'a pas résolu l'alias.
    assert models[1].label == "Claude Sonnet"
    assert seen[0].headers["authorization"] == f"Bearer {TOKEN}"


def test_un_nouvel_alias_de_la_passerelle_apparait_sans_toucher_a_l_application():
    payload = {"models": [{"id": "fable", "resolved": "claude-fable-5-2"}, {"description": "?"}]}

    models = build(gateway(models=(200, payload))).list_models()

    assert [model.identifier for model in models] == ["fable"]


@pytest.mark.parametrize(
    ("models", "attendu"),
    [
        ((401, {"error": "jeton invalide"}), "Jeton refusé"),
        ((404, {"error": "introuvable"}), "/v1/models absente"),
        ((200, {"models": "pas une liste"}), "illisible"),
    ],
)
def test_une_liste_des_modeles_inexploitable_est_expliquee(models, attendu):
    with pytest.raises(ProviderError, match=attendu):
        build(gateway(models=models)).list_models()


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


# --------------------------------------------------------------------------- #
# Choix du modèle par menu déroulant
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_le_modele_se_choisit_dans_un_menu_des_le_premier_affichage(staff_client):
    """Catalogue fermé : rien à attendre du réseau ni d'une configuration enregistrée."""
    content = staff_client.get(reverse("aiproviders:edit", args=["claude_gateway"])).content
    content = " ".join(content.decode().split())

    assert '<select name="default_model"' in content
    for identifier in ("haiku", "sonnet", "opus"):
        assert f'value="{identifier}"' in content
    assert "Par défaut (sonnet)" in content
    # Pas de chargement différé : la liste est déjà là.
    assert reverse("aiproviders:models", args=["claude_gateway"]) not in content


@pytest.mark.django_db
def test_une_fois_configuree_la_liste_se_charge_depuis_la_passerelle(staff_client):
    """Issue #156 : le catalogue distant arrive en différé, comme celui de Gemini."""
    ProviderCredential.objects.create(
        provider="claude_gateway", secret=TOKEN, base_url=BASE_URL, default_model="haiku"
    )

    content = staff_client.get(reverse("aiproviders:edit", args=["claude_gateway"])).content
    content = " ".join(content.decode().split())

    assert reverse("aiproviders:models", args=["claude_gateway"]) in content
    assert 'hx-trigger="load"' in content


def _menu(staff_client, monkeypatch, list_models) -> str:
    ProviderCredential.objects.create(
        provider="claude_gateway", secret=TOKEN, base_url=BASE_URL, default_model="haiku"
    )
    monkeypatch.setattr(ClaudeGatewayClient, "list_models", list_models)
    content = staff_client.get(reverse("aiproviders:models", args=["claude_gateway"])).content
    return " ".join(content.decode().split())


@pytest.mark.django_db
def test_le_menu_charge_propose_le_modele_reel_et_preselectionne(staff_client, monkeypatch):
    content = _menu(
        staff_client,
        monkeypatch,
        lambda self: [
            ModelOption("haiku", "Claude Haiku — claude-haiku-5-5"),
            ModelOption("fable", "Claude Fable — claude-fable-5-2"),
        ],
    )

    assert '<select name="default_model"' in content
    assert '<option value="haiku" selected> Claude Haiku — claude-haiku-5-5 </option>' in content
    assert 'value="fable"' in content


@pytest.mark.django_db
def test_une_panne_retombe_sur_les_modeles_connus(staff_client, monkeypatch):
    """Mieux qu'une saisie libre : le catalogue de repli reste un menu."""

    def tombe_en_panne(self):
        raise ProviderError("Passerelle occupée.")

    content = _menu(staff_client, monkeypatch, tombe_en_panne)

    assert "Passerelle occupée." in content
    assert '<select name="default_model"' in content
    for identifier in ("haiku", "sonnet", "opus"):
        assert f'value="{identifier}"' in content
    assert "Les modèles connus sont proposés à la place" in content
    assert "Réessayer" in content


@pytest.mark.django_db
def test_une_liste_vide_retombe_aussi_sur_les_modeles_connus(staff_client, monkeypatch):
    content = _menu(staff_client, monkeypatch, lambda self: [])

    assert '<select name="default_model"' in content
    assert "n'a renvoyé aucun modèle" in content


@pytest.mark.django_db
def test_un_alias_lu_sur_la_passerelle_s_enregistre(staff_client):
    """Une fois configurée, le champ accepte les alias que publie la passerelle."""
    ProviderCredential.objects.create(provider="claude_gateway", secret=TOKEN, base_url=BASE_URL)

    response = staff_client.post(
        reverse("aiproviders:edit", args=["claude_gateway"]),
        {"secret": "", "base_url": BASE_URL, "default_model": "fable", "is_active": "on"},
    )

    assert response.status_code == 302
    assert ProviderCredential.objects.get(provider="claude_gateway").default_model == "fable"


@pytest.mark.django_db
def test_un_modele_hors_catalogue_est_refuse():
    form = ProviderCredentialForm(
        {"secret": TOKEN, "base_url": BASE_URL, "default_model": "gpt-5", "is_active": "on"},
        spec=get_spec("claude_gateway"),
    )

    assert not form.is_valid()
    assert "default_model" in form.errors


@pytest.mark.django_db
def test_le_choix_par_defaut_suit_le_modele_du_registre():
    form = ProviderCredentialForm(
        {"secret": TOKEN, "base_url": BASE_URL, "default_model": "", "is_active": "on"},
        spec=get_spec("claude_gateway"),
    )

    assert form.is_valid()
    credential = form.save(commit=False)
    credential.provider = "claude_gateway"  # posé par la vue, comme à l'enregistrement
    assert credential.default_model == ""
    assert credential.effective_model == "sonnet"
