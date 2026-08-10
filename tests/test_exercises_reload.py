"""Rechargement du référentiel à la demande, hors du premier amorçage (issue #29)."""

import pytest
from django.urls import reverse

from aiproviders.models import ProviderCredential
from exercises import catalog
from exercises.models import Exercise

pytestmark = pytest.mark.django_db

TOTAL = 4


# --------------------------------------------------------------------------- #
# Accès
# --------------------------------------------------------------------------- #


def test_la_page_exige_une_authentification(client):
    response = client.get(reverse("exercises:reload"))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_un_utilisateur_ordinaire_ne_peut_pas_recharger(logged_client):
    """Recharger avec traduction consomme des jetons IA : réservé au personnel."""
    response = logged_client.get(reverse("exercises:reload"))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_le_personnel_accede_a_l_ecran(staff_client):
    assert staff_client.get(reverse("exercises:reload")).status_code == 200


def test_le_lot_est_reserve_au_personnel(logged_client):
    response = logged_client.post(reverse("exercises:reload_batch"), {"offset": 0})

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_le_lot_refuse_la_methode_get(staff_client):
    assert staff_client.get(reverse("exercises:reload_batch")).status_code == 405


# --------------------------------------------------------------------------- #
# Bandeau IA
# --------------------------------------------------------------------------- #


def test_sans_fournisseur_seul_un_rechargement_simple_est_propose(staff_client):
    content = staff_client.get(reverse("exercises:reload")).content.decode()

    assert "Aucun fournisseur IA actif" in content
    assert "Recharger avec traduction" not in content
    assert "Recharger le référentiel" in content


def test_avec_un_fournisseur_le_bandeau_le_nomme(staff_client):
    ProviderCredential.objects.create(
        provider="anthropic", secret="sk-test", default_model="claude-opus-5", is_active=True
    )

    content = staff_client.get(reverse("exercises:reload")).content.decode()

    assert "Anthropic (Claude)" in content
    assert "claude-opus-5" in content
    assert "consommer des jetons IA" in content
    assert "Recharger avec traduction" in content
    assert "Recharger sans traduction" in content


# --------------------------------------------------------------------------- #
# Progression
# --------------------------------------------------------------------------- #


def test_lecran_annonce_le_volume_du_referentiel(staff_client):
    content = staff_client.get(reverse("exercises:reload")).content.decode()

    assert str(TOTAL) in content


def test_un_lot_complet_signale_le_referentiel_a_jour(staff_client):
    content = staff_client.post(
        reverse("exercises:reload_batch"), {"offset": 0, "translate": "0"}
    ).content.decode()

    assert 'aria-valuenow="100"' in content
    assert "Référentiel à jour" in content
    assert Exercise.objects.count() == TOTAL


def test_un_lot_non_final_reclame_le_suivant(staff_client, monkeypatch):
    monkeypatch.setattr(catalog, "BATCH_SIZE", 2)

    content = staff_client.post(
        reverse("exercises:reload_batch"), {"offset": 0, "translate": "0"}
    ).content.decode()

    assert 'aria-valuenow="50"' in content
    assert reverse("exercises:reload_batch") in content
    assert '"offset": 2' in content


def test_le_referentiel_deja_charge_ne_bloque_pas_le_rechargement(staff_client):
    """Contrairement à l'amorçage, le compte de lignes est déjà complet dès le départ."""
    assert Exercise.objects.count() == TOTAL

    content = staff_client.post(
        reverse("exercises:reload_batch"), {"offset": 0, "translate": "0"}
    ).content.decode()

    assert 'aria-valuenow="100"' in content


def test_la_traduction_se_propage_d_un_lot_a_l_autre(staff_client, monkeypatch):
    monkeypatch.setattr(catalog, "BATCH_SIZE", 2)

    content = staff_client.post(
        reverse("exercises:reload_batch"), {"offset": 0, "translate": "1"}
    ).content.decode()

    assert '"translate": "1"' in content


def test_le_dernier_lot_traduit_le_signale(staff_client, monkeypatch):
    monkeypatch.setattr(catalog.translation, "translate_instructions", lambda instructions: None)

    content = staff_client.post(
        reverse("exercises:reload_batch"), {"offset": 0, "translate": "1"}
    ).content.decode()

    assert "traduction incluse" in content


def test_une_source_illisible_est_annoncee_sans_bloquer(staff_client, settings, tmp_path):
    settings.EXERCISES_SOURCE = str(tmp_path / "introuvable.json")

    content = staff_client.post(
        reverse("exercises:reload_batch"), {"offset": 0, "translate": "0"}
    ).content.decode()

    assert "introuvable" in content
