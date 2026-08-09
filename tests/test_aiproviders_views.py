"""Page de configuration des fournisseurs d'IA."""

import pytest
from django.urls import reverse

from aiproviders.clients.base import PingResult
from aiproviders.models import ProviderCredential

SECRET = "sk-ant-secret-de-test-f3a9"


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
    monkeypatch.setattr(
        "aiproviders.views.get_client",
        lambda credential: type(
            "Stub", (), {"ping": lambda self: PingResult(True, "Connexion établie — Claude.")}
        )(),
    )

    response = staff_client.post(reverse("aiproviders:test", args=["anthropic"]))

    assert response.status_code == 200
    assert "Connexion établie" in response.content.decode()


@pytest.mark.django_db
def test_le_test_de_connexion_signale_un_fournisseur_non_configure(staff_client):
    response = staff_client.post(reverse("aiproviders:test", args=["mistral"]))

    assert "n&#x27;est pas encore configuré" in response.content.decode()
