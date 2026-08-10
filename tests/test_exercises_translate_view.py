"""Traduction unitaire d'une fiche, à la demande, depuis le catalogue ou une séance (issue #31)."""

import json

import pytest
from django.urls import reverse

from exercises.models import Exercise

pytestmark = pytest.mark.django_db


def stub_client(monkeypatch, generate):
    """Fournisseur actif simulé, pour le calcul de `can_translate` et l'appel réel."""
    stub = type("Stub", (), {"generate": generate})()
    monkeypatch.setattr("exercises.views.get_active_client", lambda: stub)
    monkeypatch.setattr("exercises.translation.get_active_client", lambda: stub)


# --------------------------------------------------------------------------- #
# Accès
# --------------------------------------------------------------------------- #


def test_la_traduction_exige_une_authentification(client):
    squat = Exercise.objects.get(slug="Barbell_Squat")
    response = client.post(reverse("exercises:translate", args=[squat.pk]))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_un_utilisateur_ordinaire_peut_traduire(logged_client, monkeypatch):
    """Contrairement au rechargement en masse, un seul appel n'est pas réservé au personnel."""
    squat = Exercise.objects.get(slug="Barbell_Squat")
    stub_client(monkeypatch, lambda self, prompt, **kwargs: '["Traduit."] ')

    response = logged_client.post(reverse("exercises:translate", args=[squat.pk]))

    assert response.status_code == 200


def test_la_traduction_refuse_la_methode_get(logged_client):
    squat = Exercise.objects.get(slug="Barbell_Squat")

    assert logged_client.get(reverse("exercises:translate", args=[squat.pk])).status_code == 405


# --------------------------------------------------------------------------- #
# Traduction
# --------------------------------------------------------------------------- #


def test_une_fiche_est_traduite_et_enregistree(logged_client, monkeypatch):
    squat = Exercise.objects.get(slug="Barbell_Squat")
    traduit = ["Un.", "Deux.", "Trois."]
    stub_client(monkeypatch, lambda self, prompt, **kwargs: json.dumps(traduit))

    content = logged_client.post(reverse("exercises:translate", args=[squat.pk])).content.decode()

    squat.refresh_from_db()
    assert squat.instructions_fr == traduit
    assert "Un." in content
    assert "Traduire cette fiche" not in content


def test_une_fiche_deja_traduite_n_est_pas_redemandee(logged_client, monkeypatch):
    squat = Exercise.objects.get(slug="Barbell_Squat")
    squat.instructions_fr = ["Déjà traduit."]
    squat.save()

    def refuser(self, prompt, **kwargs):
        raise AssertionError("le fournisseur ne doit pas être appelé")

    stub_client(monkeypatch, refuser)

    content = logged_client.post(reverse("exercises:translate", args=[squat.pk])).content.decode()

    assert "Déjà traduit." in content


def test_un_echec_de_traduction_est_signale(logged_client, monkeypatch):
    squat = Exercise.objects.get(slug="Barbell_Squat")
    stub_client(monkeypatch, lambda self, prompt, **kwargs: "pas du json")

    content = logged_client.post(reverse("exercises:translate", args=[squat.pk])).content.decode()

    squat.refresh_from_db()
    assert squat.instructions_fr == []
    assert "indisponible" in content
    # Le bouton reste affiché : l'utilisateur doit pouvoir réessayer.
    assert "Traduire cette fiche" in content


def test_sans_fournisseur_rien_n_est_tente(logged_client):
    """Le bouton ne devrait jamais pointer ici sans fournisseur, mais l'action reste sûre."""
    squat = Exercise.objects.get(slug="Barbell_Squat")

    content = logged_client.post(reverse("exercises:translate", args=[squat.pk])).content.decode()

    squat.refresh_from_db()
    assert squat.instructions_fr == []
    assert "indisponible" in content


# --------------------------------------------------------------------------- #
# Affichage du bouton — catalogue
# --------------------------------------------------------------------------- #


def test_sans_fournisseur_le_bouton_n_apparait_pas(logged_client):
    content = logged_client.get(reverse("exercises:list")).content.decode()

    assert "Traduire cette fiche" not in content


def test_avec_un_fournisseur_le_bouton_apparait_pour_une_fiche_non_traduite(
    logged_client, monkeypatch
):
    stub_client(monkeypatch, lambda self, prompt, **kwargs: "[]")

    content = logged_client.get(reverse("exercises:list")).content.decode()

    assert "Traduire cette fiche" in content


def test_une_fiche_deja_traduite_ne_propose_pas_le_bouton(logged_client, monkeypatch):
    """Barbell_Squat, Calf_Stretch et Dumbbell_Bench_Press ont des consignes non
    traduites (voir tests/fixtures/exercises.json) : marquer la première traduite
    doit faire passer le nombre de boutons de trois à deux."""
    stub_client(monkeypatch, lambda self, prompt, **kwargs: "[]")

    avant = logged_client.get(reverse("exercises:list")).content.decode()
    assert avant.count("Traduire cette fiche") == 3

    squat = Exercise.objects.get(slug="Barbell_Squat")
    squat.instructions_fr = ["Déjà traduit."]
    squat.save()

    apres = logged_client.get(reverse("exercises:list")).content.decode()
    assert apres.count("Traduire cette fiche") == 2
