"""Écran de chargement du catalogue : redirection d'amorçage et progression."""

import pytest
from django.urls import reverse

from exercises import catalog
from exercises.models import Exercise

pytestmark = pytest.mark.django_db

TOTAL = 4


# --------------------------------------------------------------------------- #
# Redirection tant que le catalogue manque
# --------------------------------------------------------------------------- #


@pytest.mark.empty_catalog
@pytest.mark.parametrize("route", ["core:home", "accounts:profile"])
def test_sans_catalogue_les_pages_menent_au_chargement(client, route):
    response = client.get(reverse(route))

    assert response.status_code == 302
    assert response.url == reverse("exercises:loading")


@pytest.mark.empty_catalog
def test_la_connexion_reste_joignable_pendant_l_amorcage(client):
    """L'écran de chargement exige un compte : sans exemption, la redirection boucle."""
    assert client.get(reverse("accounts:login")).status_code == 200


@pytest.mark.empty_catalog
def test_la_sonde_de_sante_reste_joignable_sans_catalogue(client):
    assert client.get(reverse("core:healthz")).status_code == 200


def test_l_ecran_disparait_une_fois_le_catalogue_charge(logged_client):
    response = logged_client.get(reverse("exercises:loading"))

    assert response.status_code == 302
    assert response.url == reverse("core:home")


@pytest.mark.empty_catalog
def test_le_chargement_exige_une_authentification(client):
    response = client.get(reverse("exercises:loading"))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


# --------------------------------------------------------------------------- #
# Progression
# --------------------------------------------------------------------------- #


@pytest.mark.empty_catalog
def test_l_ecran_annonce_le_volume_a_charger(logged_client):
    content = logged_client.get(reverse("exercises:loading")).content.decode()

    assert str(TOTAL) in content
    # Règle graphique : barre chiffrée pour un traitement borné.
    assert 'role="progressbar"' in content
    assert 'aria-valuenow="0"' in content


@pytest.mark.empty_catalog
def test_un_lot_importe_et_rend_la_progression(logged_client):
    response = logged_client.post(reverse("exercises:load_batch"), {"offset": 0})
    content = response.content.decode()

    assert Exercise.objects.count() == TOTAL
    assert 'aria-valuenow="100"' in content


@pytest.mark.empty_catalog
def test_un_lot_non_final_reclame_le_suivant(logged_client, monkeypatch):
    """La chaîne de tranches ne doit pas s'interrompre avant la fin."""
    monkeypatch.setattr(catalog, "BATCH_SIZE", 2)

    content = logged_client.post(reverse("exercises:load_batch"), {"offset": 0}).content.decode()

    assert Exercise.objects.count() == 2
    assert 'aria-valuenow="50"' in content
    assert reverse("exercises:load_batch") in content
    assert '"offset": 2' in content


def test_le_dernier_lot_propose_de_continuer(logged_client):
    content = logged_client.post(
        reverse("exercises:load_batch"), {"offset": TOTAL}
    ).content.decode()

    assert 'aria-valuenow="100"' in content
    assert reverse("core:home") in content
    # Plus rien à demander : la chaîne s'arrête.
    assert reverse("exercises:load_batch") not in content


@pytest.mark.empty_catalog
def test_un_offset_illisible_repart_du_debut(logged_client):
    """La position vient du navigateur : elle n'est jamais utilisée telle quelle."""
    response = logged_client.post(reverse("exercises:load_batch"), {"offset": "n'importe quoi"})

    assert response.status_code == 200
    assert Exercise.objects.count() == TOTAL


@pytest.mark.empty_catalog
def test_le_chargement_par_lot_refuse_la_methode_get(logged_client):
    assert logged_client.get(reverse("exercises:load_batch")).status_code == 405


@pytest.mark.empty_catalog
def test_une_source_illisible_est_annoncee_sans_bloquer(logged_client, settings, tmp_path):
    settings.EXERCISES_SOURCE = str(tmp_path / "introuvable.json")

    content = logged_client.post(reverse("exercises:load_batch"), {"offset": 0}).content.decode()

    assert "introuvable" in content
    assert reverse("core:home") in content
