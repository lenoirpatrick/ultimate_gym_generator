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


def test_la_carte_du_catalogue_propose_la_bascule(logged_client, squat):
    content = logged_client.get(reverse("exercises:list")).content.decode()

    assert reverse("exercises:toggle_unavailable", args=[squat.pk]) in content


def test_la_carte_d_un_exercice_ecarte_montre_l_etat_actif(logged_client, user, squat):
    UnavailableExercise.objects.create(user=user, exercise=squat)

    content = logged_client.get(reverse("exercises:list")).content.decode()

    assert f'id="materiel-absent-{squat.pk}"' in content
    assert "Barbell Squat" in content


def test_la_bascule_ecarte_puis_retablit(logged_client, user, squat):
    url = reverse("exercises:toggle_unavailable", args=[squat.pk])

    response = logged_client.post(url)

    assert response.status_code == 200
    assert 'aria-pressed="true"' in response.content.decode()
    assert UnavailableExercise.objects.filter(user=user, exercise=squat).exists()

    response = logged_client.post(url)

    assert 'aria-pressed="false"' in response.content.decode()
    assert not UnavailableExercise.objects.filter(user=user).exists()


def test_la_bascule_ne_touche_pas_aux_exclusions_d_un_autre(logged_client, user, staff, squat):
    UnavailableExercise.objects.create(user=staff, exercise=squat)

    logged_client.post(reverse("exercises:toggle_unavailable", args=[squat.pk]))

    assert UnavailableExercise.objects.filter(user=staff, exercise=squat).exists()
    assert UnavailableExercise.objects.filter(user=user, exercise=squat).exists()


def test_la_bascule_exige_une_requete_post(logged_client, squat):
    response = logged_client.get(reverse("exercises:toggle_unavailable", args=[squat.pk]))

    assert response.status_code == 405


def test_la_bascule_d_un_exercice_inconnu_echoue_proprement(logged_client):
    response = logged_client.post(reverse("exercises:toggle_unavailable", args=[999_999]))

    assert response.status_code == 404


def test_retablir_exige_une_authentification(client, squat):
    response = client.post(reverse("exercises:restore_unavailable", args=[squat.pk]))

    assert response.status_code == 302
