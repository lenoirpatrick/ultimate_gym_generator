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


def test_le_formulaire_affiche_les_regions_du_corps(logged_client):
    """Découpage en quatre régions plutôt qu'une liste plate de dix-sept muscles."""
    content = logged_client.get(reverse("workouts:create")).content.decode()

    for region in ("Haut du corps", "Dos", "Tronc", "Bas du corps"):
        assert region in content


def test_le_formulaire_affiche_une_bulle_d_aide_par_format(logged_client):
    content = logged_client.get(reverse("workouts:create")).content.decode()

    assert content.count("ugg-hint__bubble") == 4
    assert "Huit séries d&#x27;un seul exercice" in content


def test_les_temps_personnalises_sont_transmis_et_enregistres(logged_client, user):
    composer(
        logged_client,
        workout_format=Workout.Format.HIIT,
        work_hiit="30",
        rest_hiit="45",
    )

    workout = Workout.objects.get(user=user)
    assert (workout.work_seconds, workout.rest_seconds) == (30, 45)
    assert workout.items.first().rest_seconds == 45


def test_les_temps_d_un_format_non_retenu_n_empechent_pas_l_envoi(logged_client, user):
    """Régler Tabata puis composer un Circuit ne doit pas être bloqué par Tabata."""
    composer(
        logged_client,
        workout_format=Workout.Format.CIRCUIT,
        work_tabata="9999",
        rest_tabata="-5",
    )

    assert Workout.objects.filter(user=user).exists()


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
# Favori (issue #26)
# --------------------------------------------------------------------------- #


def test_une_seance_se_marque_favorite(logged_client, user):
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    response = logged_client.post(reverse("workouts:toggle_favorite", args=[workout.pk]))

    workout.refresh_from_db()
    assert workout.is_favorite is True
    assert 'aria-pressed="true"' in response.content.decode()


def test_la_bascule_favori_est_reversible(logged_client, user):
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    logged_client.post(reverse("workouts:toggle_favorite", args=[workout.pk]))
    logged_client.post(reverse("workouts:toggle_favorite", args=[workout.pk]))

    workout.refresh_from_db()
    assert workout.is_favorite is False


def test_la_bascule_favori_refuse_la_methode_get(logged_client, user):
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    assert (
        logged_client.get(reverse("workouts:toggle_favorite", args=[workout.pk])).status_code == 405
    )


def test_on_ne_bascule_pas_le_favori_d_un_autre(logged_client, staff_client, user):
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    response = staff_client.post(reverse("workouts:toggle_favorite", args=[workout.pk]))

    assert response.status_code == 404
    assert not Workout.objects.get(pk=workout.pk).is_favorite


def test_le_filtre_favoris_ne_garde_que_les_seances_marquees(logged_client, user):
    composer(logged_client)
    composer(logged_client, workout_format=Workout.Format.TABATA)
    marque = Workout.objects.filter(user=user).first()
    logged_client.post(reverse("workouts:toggle_favorite", args=[marque.pk]))

    content = logged_client.get(reverse("workouts:list"), {"favoris": "1"}).content.decode()

    assert content.count(reverse("workouts:detail", args=[marque.pk])) >= 1
    autre = Workout.objects.filter(user=user).exclude(pk=marque.pk).first()
    assert reverse("workouts:detail", args=[autre.pk]) not in content


def test_sans_favori_le_filtre_invite_a_en_marquer_un(logged_client, user):
    composer(logged_client)

    content = logged_client.get(reverse("workouts:list"), {"favoris": "1"}).content.decode()

    assert "Aucun favori" in content


# --------------------------------------------------------------------------- #
# Nom (issue #28)
# --------------------------------------------------------------------------- #


def test_une_seance_sans_nom_affiche_le_format(logged_client, user):
    composer(logged_client, workout_format=Workout.Format.TABATA)
    workout = Workout.objects.get(user=user)

    assert workout.display_name == workout.get_format_display()

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()
    assert workout.get_format_display() in content


def test_une_seance_se_renomme(logged_client, user):
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    response = logged_client.post(
        reverse("workouts:rename", args=[workout.pk]),
        {"name": "Jambes du lundi"},
        follow=True,
    )

    workout.refresh_from_db()
    assert workout.name == "Jambes du lundi"
    assert workout.display_name == "Jambes du lundi"
    assert "Jambes du lundi" in response.content.decode()


def test_le_nom_est_debarrasse_des_espaces_superflus(logged_client, user):
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    logged_client.post(reverse("workouts:rename", args=[workout.pk]), {"name": "  Dos  "})

    workout.refresh_from_db()
    assert workout.name == "Dos"


def test_un_nom_vide_revient_au_format(logged_client, user):
    composer(logged_client)
    workout = Workout.objects.get(user=user)
    logged_client.post(reverse("workouts:rename", args=[workout.pk]), {"name": "Jambes"})

    logged_client.post(reverse("workouts:rename", args=[workout.pk]), {"name": ""})

    workout.refresh_from_db()
    assert workout.name == ""
    assert workout.display_name == workout.get_format_display()


def test_le_nom_est_tronque_a_la_longueur_maximale(logged_client, user):
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    logged_client.post(reverse("workouts:rename", args=[workout.pk]), {"name": "x" * 200})

    workout.refresh_from_db()
    assert len(workout.name) == 80


def test_le_format_rejoint_les_etiquettes_quand_un_nom_est_defini(logged_client, user):
    composer(logged_client, workout_format=Workout.Format.TABATA)
    workout = Workout.objects.get(user=user)
    logged_client.post(reverse("workouts:rename", args=[workout.pk]), {"name": "Jambes"})

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert "Jambes" in content
    assert workout.get_format_display() in content


def test_l_historique_affiche_le_nom_choisi(logged_client, user):
    composer(logged_client)
    workout = Workout.objects.get(user=user)
    logged_client.post(reverse("workouts:rename", args=[workout.pk]), {"name": "Jambes"})

    content = logged_client.get(reverse("workouts:list")).content.decode()

    assert "Jambes" in content


def test_le_renommage_refuse_la_methode_get(logged_client, user):
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    assert logged_client.get(reverse("workouts:rename", args=[workout.pk])).status_code == 405


def test_on_ne_renomme_pas_la_seance_d_un_autre(logged_client, staff_client, user):
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    response = staff_client.post(reverse("workouts:rename", args=[workout.pk]), {"name": "Piraté"})

    assert response.status_code == 404
    assert Workout.objects.get(pk=workout.pk).name == ""


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
