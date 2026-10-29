"""Exercices écartés faute de matériel : liste et rétablissement (issue #127)."""

import pytest
from django.urls import reverse

from exercises.models import Exercise, UnavailableExercise

pytestmark = pytest.mark.django_db


@pytest.fixture
def squat():
    return Exercise.objects.get(slug="Barbell_Squat")


def test_l_ecran_materiel_liste_les_exercices_ecartes(logged_client, user, squat):
    UnavailableExercise.objects.create(user=user, exercise=squat)

    content = logged_client.get(reverse("accounts:equipment")).content.decode()

    assert "Barbell Squat" in content
    assert reverse("exercises:restore_unavailable", args=[squat.pk]) in content


def test_l_ecran_materiel_signale_l_absence_d_exercice_ecarte(logged_client):
    content = logged_client.get(reverse("accounts:equipment")).content.decode()

    assert "Aucun exercice écarté" in content


def test_l_ecran_materiel_n_affiche_que_ses_propres_exclusions(logged_client, staff, squat):
    UnavailableExercise.objects.create(user=staff, exercise=squat)

    content = logged_client.get(reverse("accounts:equipment")).content.decode()

    assert "Aucun exercice écarté" in content


def test_un_exercice_ecarte_se_retablit(logged_client, user, squat):
    UnavailableExercise.objects.create(user=user, exercise=squat)

    response = logged_client.post(reverse("exercises:restore_unavailable", args=[squat.pk]))

    assert response.status_code == 200
    assert not UnavailableExercise.objects.filter(user=user).exists()
    assert "Aucun exercice écarté" in response.content.decode()


def test_retablir_ne_touche_pas_aux_exclusions_d_un_autre(logged_client, staff, squat):
    UnavailableExercise.objects.create(user=staff, exercise=squat)

    logged_client.post(reverse("exercises:restore_unavailable", args=[squat.pk]))

    assert UnavailableExercise.objects.filter(user=staff, exercise=squat).exists()


def test_retablir_exige_une_requete_post(logged_client, squat):
    response = logged_client.get(reverse("exercises:restore_unavailable", args=[squat.pk]))

    assert response.status_code == 405


def test_retablir_exige_une_authentification(client, squat):
    response = client.post(reverse("exercises:restore_unavailable", args=[squat.pk]))

    assert response.status_code == 302
