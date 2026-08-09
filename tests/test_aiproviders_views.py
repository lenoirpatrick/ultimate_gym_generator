"""Page de configuration des fournisseurs d'IA."""

import re

import pytest
from django.urls import reverse

from aiproviders.clients.base import ModelOption, PingResult, ProviderError
from aiproviders.models import ProviderCredential

SECRET = "sk-ant-secret-de-test-f3a9"


def stub_client(monkeypatch, **methods):
    """Remplace l'adaptateur par un double : aucun test ne doit sortir sur le réseau."""
    monkeypatch.setattr(
        "aiproviders.views.get_client",
        lambda credential: type("Stub", (), methods)(),
    )


def balises(response) -> str:
    """Rend le HTML sur une ligne, pour des assertions indifférentes à l'indentation."""
    return re.sub(r"\s+", " ", response.content.decode())


@pytest.mark.django_db
def test_la_page_exige_une_authentification(client):
    response = client.get(reverse("aiproviders:list"))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_un_utilisateur_ordinaire_ne_peut_pas_lire_les_credentials(logged_client):
    """Les clés valent pour toute l'installation : elles ne regardent que le personnel."""
    response = logged_client.get(reverse("aiproviders:list"))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_la_page_liste_tous_les_fournisseurs_du_registre(staff_client):
    content = staff_client.get(reverse("aiproviders:list")).content.decode()

    for name in ("Anthropic", "Gemini", "Mistral", "Ollama"):
        assert name in content


@pytest.mark.django_db
def test_le_secret_n_est_jamais_rendu_en_clair(staff_client):
    ProviderCredential.objects.create(provider="anthropic", secret=SECRET)

    listing = staff_client.get(reverse("aiproviders:list")).content.decode()
    form = staff_client.get(reverse("aiproviders:edit", args=["anthropic"])).content.decode()

    assert SECRET not in listing
    assert SECRET not in form


@pytest.mark.django_db
def test_un_champ_secret_vide_conserve_la_cle_enregistree(staff_client):
    ProviderCredential.objects.create(provider="anthropic", secret=SECRET)

    staff_client.post(
        reverse("aiproviders:edit", args=["anthropic"]),
        {"secret": "", "base_url": "", "default_model": "claude-opus-5", "is_active": "on"},
    )

    credential = ProviderCredential.objects.get(provider="anthropic")
    assert credential.secret == SECRET
    assert credential.default_model == "claude-opus-5"


@pytest.mark.django_db
def test_un_fournisseur_inconnu_renvoie_404(staff_client):
    assert staff_client.get(reverse("aiproviders:edit", args=["inexistant"])).status_code == 404


@pytest.mark.django_db
def test_le_test_de_connexion_rend_le_resultat_de_l_adaptateur(staff_client, monkeypatch):
    ProviderCredential.objects.create(provider="anthropic", secret=SECRET)
    stub_client(monkeypatch, ping=lambda self: PingResult(True, "Connexion établie — Claude."))

    response = staff_client.post(reverse("aiproviders:test", args=["anthropic"]))

    assert response.status_code == 200
    assert "Connexion établie" in response.content.decode()


@pytest.mark.django_db
def test_le_test_de_connexion_signale_un_fournisseur_non_configure(staff_client):
    response = staff_client.post(reverse("aiproviders:test", args=["mistral"]))

    assert "n&#x27;est pas encore configuré" in response.content.decode()


# --------------------------------------------------------------------------- #
# Choix du modèle (issue #7)
# --------------------------------------------------------------------------- #

GEMINI_MODELS = [
    ModelOption("gemini-2.5-pro", "Gemini 2.5 Pro"),
    ModelOption("gemini-2.5-flash", "Gemini 2.5 Flash"),
]


@pytest.mark.django_db
def test_le_choix_des_modeles_est_reserve_au_personnel(logged_client):
    response = logged_client.get(reverse("aiproviders:models", args=["gemini"]))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_un_fournisseur_qui_ne_publie_pas_son_catalogue_renvoie_404(staff_client):
    """Anthropic n'annonce pas `supports_model_listing` : la route n'a pas de sens."""
    response = staff_client.get(reverse("aiproviders:models", args=["anthropic"]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_les_modeles_disponibles_sont_proposes_dans_un_menu_deroulant(staff_client, monkeypatch):
    ProviderCredential.objects.create(
        provider="gemini", secret=SECRET, default_model="gemini-2.5-flash"
    )
    stub_client(monkeypatch, list_models=lambda self: GEMINI_MODELS)

    content = balises(staff_client.get(reverse("aiproviders:models", args=["gemini"])))

    assert '<select name="default_model"' in content
    assert 'value="gemini-2.5-pro"' in content
    # Le modèle déjà enregistré doit revenir présélectionné.
    assert 'value="gemini-2.5-flash" selected' in content


@pytest.mark.django_db
def test_le_formulaire_gemini_charge_les_modeles_en_differe(staff_client):
    """L'écran ne doit pas attendre un appel réseau pour s'afficher."""
    ProviderCredential.objects.create(provider="gemini", secret=SECRET)

    content = balises(staff_client.get(reverse("aiproviders:edit", args=["gemini"])))

    assert reverse("aiproviders:models", args=["gemini"]) in content
    assert 'hx-trigger="load"' in content
    # Règle graphique : icône de sport animée, jamais de spinner générique.
    assert "ugg-spinner--dumbbell" in content
    # `{# … #}` ne commente qu'une ligne : un commentaire multiligne écrit ainsi
    # se retrouverait affiché tel quel au milieu du formulaire.
    assert "{#" not in content


@pytest.mark.django_db
def test_une_panne_du_fournisseur_laisse_le_modele_saisissable(staff_client, monkeypatch):
    ProviderCredential.objects.create(provider="gemini", secret=SECRET)

    def tombe_en_panne(self):
        raise ProviderError("Serveur injoignable.")

    stub_client(monkeypatch, list_models=tombe_en_panne)

    content = balises(staff_client.get(reverse("aiproviders:models", args=["gemini"])))

    assert "Serveur injoignable." in content
    assert '<input type="text" name="default_model"' in content
    assert "Réessayer" in content


@pytest.mark.django_db
def test_sans_cle_enregistree_le_modele_reste_une_saisie_libre(staff_client):
    content = balises(staff_client.get(reverse("aiproviders:models", args=["gemini"])))

    assert "Enregistre d&#x27;abord une clé" in content
    assert "<select" not in content
