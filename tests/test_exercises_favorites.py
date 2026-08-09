"""Favoris : bascule, cloisonnement par utilisateur, filtre et page dédiée."""

import re

import pytest
from django.http import QueryDict
from django.urls import reverse

from exercises import filters
from exercises.models import Exercise, Favorite

pytestmark = pytest.mark.django_db


def noms(response) -> list[str]:
    return re.findall(r'<h3 class="ugg-title text-base">([^<]+)</h3>', response.content.decode())


@pytest.fixture
def squat():
    return Exercise.objects.get(slug="Barbell_Squat")


def basculer(client, exercise):
    return client.post(reverse("exercises:toggle_favorite", args=[exercise.pk]))


# --------------------------------------------------------------------------- #
# Bascule
# --------------------------------------------------------------------------- #


def test_la_bascule_exige_une_authentification(client, squat):
    response = basculer(client, squat)

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_la_bascule_refuse_la_methode_get(logged_client, squat):
    url = reverse("exercises:toggle_favorite", args=[squat.pk])

    assert logged_client.get(url).status_code == 405


def test_un_exercice_se_marque_puis_se_retire(logged_client, squat, user):
    basculer(logged_client, squat)
    assert Favorite.objects.filter(user=user, exercise=squat).exists()

    basculer(logged_client, squat)
    assert not Favorite.objects.filter(user=user, exercise=squat).exists()


def test_la_bascule_rend_le_bouton_dans_son_nouvel_etat(logged_client, squat):
    ajout = basculer(logged_client, squat).content.decode()
    assert 'aria-pressed="true"' in ajout
    assert "Retirer des favoris" in ajout

    retrait = basculer(logged_client, squat).content.decode()
    assert 'aria-pressed="false"' in retrait
    assert "Ajouter aux favoris" in retrait


def test_deux_marquages_ne_creent_pas_deux_lignes(logged_client, squat, user):
    """La contrainte d'unicité protège du double clic."""
    basculer(logged_client, squat)
    Favorite.objects.get_or_create(user=user, exercise=squat)

    assert Favorite.objects.filter(user=user, exercise=squat).count() == 1


def test_un_exercice_inexistant_renvoie_404(logged_client):
    assert (
        logged_client.post(reverse("exercises:toggle_favorite", args=[999_999])).status_code == 404
    )


def test_les_favoris_sont_cloisonnes_par_utilisateur(logged_client, staff_client, squat, user):
    """Les favoris de l'un ne doivent jamais apparaître chez l'autre."""
    basculer(logged_client, squat)

    response = staff_client.get(reverse("exercises:favorites"))

    assert noms(response) == []
    assert Favorite.objects.filter(user=user).count() == 1


# --------------------------------------------------------------------------- #
# Affichage dans le catalogue
# --------------------------------------------------------------------------- #


def test_chaque_carte_porte_la_bascule(logged_client):
    content = logged_client.get(reverse("exercises:list")).content.decode()

    assert content.count("Ajouter aux favoris") == Exercise.objects.count()


def test_l_etat_favori_apparait_dans_le_catalogue(logged_client, squat):
    basculer(logged_client, squat)

    content = logged_client.get(reverse("exercises:list")).content.decode()

    assert "Retirer des favoris" in content


def test_le_libelle_accompagne_toujours_l_etoile(logged_client):
    """Une icône seule ne dit pas si elle montre l'état ou l'action (CLAUDE.md)."""
    content = logged_client.get(reverse("exercises:list")).content.decode()

    assert "aria-pressed" in content
    assert "Ajouter aux favoris" in content


# --------------------------------------------------------------------------- #
# Filtre et page dédiée
# --------------------------------------------------------------------------- #


def test_le_filtre_ne_garde_que_les_favoris(logged_client, squat):
    basculer(logged_client, squat)

    response = logged_client.get(reverse("exercises:list"), {"favoris": "1"})

    assert noms(response) == ["Barbell Squat"]


def test_le_filtre_favoris_se_cumule_avec_les_autres_criteres(logged_client, squat):
    basculer(logged_client, squat)

    response = logged_client.get(reverse("exercises:list"), {"favoris": "1", "niveau": "expert"})

    assert noms(response) == []


def test_la_case_favoris_est_conservee_a_l_affichage(logged_client):
    content = logged_client.get(reverse("exercises:list"), {"favoris": "1"}).content.decode()

    assert 'name="favoris" value="1"\n                           checked' in content.replace(
        "\r", ""
    )


def test_la_case_favoris_compte_comme_un_filtre_actif(logged_client):
    """Sinon rien ne proposerait de revenir au catalogue entier."""
    content = logged_client.get(reverse("exercises:list"), {"favoris": "1"}).content.decode()

    assert "Tout effacer" in content


def test_la_page_dediee_impose_le_filtre(logged_client, squat):
    basculer(logged_client, squat)

    response = logged_client.get(reverse("exercises:favorites"))

    assert noms(response) == ["Barbell Squat"]
    assert "Mes favoris" in response.content.decode()


def test_la_page_dediee_ne_propose_pas_la_case_favoris(logged_client):
    """Le critère y est implicite : l'offrir laisserait croire qu'on peut le retirer."""
    content = logged_client.get(reverse("exercises:favorites")).content.decode()

    assert 'name="favoris"' not in content


def test_la_page_dediee_sans_favori_invite_au_catalogue(logged_client):
    content = logged_client.get(reverse("exercises:favorites")).content.decode()

    assert "Aucun favori" in content
    assert reverse("exercises:list") in content


def test_les_filtres_de_la_page_dediee_y_restent(logged_client, squat):
    """« Tout effacer » depuis les favoris ne doit pas renvoyer au catalogue entier."""
    basculer(logged_client, squat)

    content = logged_client.get(
        reverse("exercises:favorites"), {"niveau": "beginner"}
    ).content.decode()

    assert f'action="{reverse("exercises:favorites")}"' in content


# --------------------------------------------------------------------------- #
# Efficacité
# --------------------------------------------------------------------------- #


def test_l_etat_favori_ne_coute_pas_une_requete_par_carte(django_assert_num_queries, user, squat):
    """Sans l'annotation, chaque carte interrogerait la table des favoris."""
    Favorite.objects.create(user=user, exercise=squat)
    exercises = list(filters.filter_exercises(QueryDict(), user))

    with django_assert_num_queries(0):
        assert [e.is_favorite for e in exercises].count(True) == 1
