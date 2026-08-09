"""Écrans de séance : composition, historique, cloisonnement."""

import pytest
from django.urls import reverse

from accounts.models import UserEquipment
from workouts.models import Workout

pytestmark = pytest.mark.django_db


def payload(**overrides) -> dict:
    data = {
        "duration_minutes": "20",
        "workout_format": Workout.Format.CIRCUIT,
        "favorites_ratio": "25",
    }
    return data | overrides


def composer(client, **overrides):
    return client.post(reverse("workouts:create"), payload(**overrides), follow=True)


# --------------------------------------------------------------------------- #
# Accès
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("route", ["workouts:list", "workouts:create"])
def test_les_seances_exigent_une_authentification(client, route):
    response = client.get(reverse(route))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_l_historique_est_vide_au_depart(logged_client):
    content = logged_client.get(reverse("workouts:list")).content.decode()

    assert "Aucune séance" in content


# --------------------------------------------------------------------------- #
# Composition
# --------------------------------------------------------------------------- #


def test_une_seance_se_compose_et_s_affiche(logged_client, user):
    response = composer(logged_client)

    workout = Workout.objects.get(user=user)
    assert response.request["PATH_INFO"] == reverse("workouts:detail", args=[workout.pk])
    assert workout.items.exists()


def test_le_formulaire_annonce_le_materiel_pris_en_compte(logged_client, user):
    UserEquipment.objects.create(user=user, equipment="kettlebells", mode="fixed", weights=[16])

    content = logged_client.get(reverse("workouts:create")).content.decode()

    assert "Kettlebell" in content
    assert reverse("accounts:equipment") in content


def test_sans_materiel_le_formulaire_le_dit(logged_client):
    """Mieux vaut l'annoncer que laisser croire à un catalogue complet."""
    content = logged_client.get(reverse("workouts:create")).content.decode()

    assert "Aucun matériel déclaré" in content


def test_une_demande_impossible_est_expliquee_dans_le_formulaire(logged_client, user):
    """Aucun exercice pour ce muscle sans matériel : il faut dire quoi changer."""
    from exercises.models import Muscle

    cou = Muscle.objects.get(slug="neck")
    response = logged_client.post(reverse("workouts:create"), payload(muscles=[str(cou.pk)]))

    assert response.status_code == 200
    assert "Élargis la sélection" in response.content.decode()
    assert not Workout.objects.filter(user=user).exists()


def test_un_formulaire_invalide_ne_cree_rien(logged_client, user):
    response = logged_client.post(reverse("workouts:create"), payload(duration_minutes="7"))

    assert response.status_code == 200
    assert not Workout.objects.filter(user=user).exists()


# --------------------------------------------------------------------------- #
# Consultation
# --------------------------------------------------------------------------- #


def test_la_seance_affiche_son_deroule(logged_client, user):
    composer(logged_client, workout_format=Workout.Format.TABATA)
    workout = Workout.objects.get(user=user)

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert "Bloc 1" in content
    # Le minutage doit être lisible d'un coup d'œil, entre deux séries.
    assert "20s" in content
    assert "10s repos" in content


def test_la_seance_affiche_les_charges_proposees(logged_client, user):
    UserEquipment.objects.create(
        user=user, equipment="dumbbell", mode="fixed", weights=[10, 12, 14]
    )
    composer(logged_client, muscles=[])

    workout = Workout.objects.get(user=user)
    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert "point de départ" in content


def test_l_historique_liste_les_seances(logged_client, user):
    composer(logged_client)

    content = logged_client.get(reverse("workouts:list")).content.decode()

    workout = Workout.objects.get(user=user)
    assert reverse("workouts:detail", args=[workout.pk]) in content


def test_la_seance_d_un_autre_utilisateur_est_introuvable(logged_client, staff_client, user):
    """Une séance ne se partage pas : elle n'est même pas visible."""
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    assert staff_client.get(reverse("workouts:detail", args=[workout.pk])).status_code == 404


def test_l_historique_est_cloisonne(logged_client, staff_client, user):
    composer(logged_client)

    content = staff_client.get(reverse("workouts:list")).content.decode()

    assert "Aucune séance" in content


# --------------------------------------------------------------------------- #
# Suppression
# --------------------------------------------------------------------------- #


def test_une_seance_se_supprime(logged_client, user):
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    logged_client.post(reverse("workouts:delete", args=[workout.pk]))

    assert not Workout.objects.filter(pk=workout.pk).exists()


def test_la_suppression_refuse_la_methode_get(logged_client, user):
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    assert logged_client.get(reverse("workouts:delete", args=[workout.pk])).status_code == 405


def test_on_ne_supprime_pas_la_seance_d_un_autre(logged_client, staff_client, user):
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    assert staff_client.post(reverse("workouts:delete", args=[workout.pk])).status_code == 404
    assert Workout.objects.filter(pk=workout.pk).exists()
