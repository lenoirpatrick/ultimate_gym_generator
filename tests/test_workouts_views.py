"""Écrans de séance : composition, historique, cloisonnement."""

import re

import pytest
from django.urls import reverse

from accounts.models import UserEquipment
from exercises.models import Exercise
from workouts import generator
from workouts.models import Workout, WorkoutExercise

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


# --------------------------------------------------------------------------- #
# Matériel pris en compte : sélection directe, indépendante de la
# configuration (issue #32)
# --------------------------------------------------------------------------- #


def test_le_materiel_declare_se_coche_directement_dans_l_encart(logged_client, user):
    """Une vraie case à cocher, pas une étiquette en lecture seule."""
    UserEquipment.objects.create(user=user, equipment="dumbbell", mode="fixed", weights=[10])

    content = logged_client.get(reverse("workouts:create")).content.decode()

    assert '<label class="ugg-filter__option ugg-filter__option--standalone">' in content
    assert 'type="checkbox" name="equipment" value="dumbbell"' in content


def test_le_materiel_declare_est_coche_par_defaut(logged_client, user):
    UserEquipment.objects.create(user=user, equipment="dumbbell", mode="fixed", weights=[10])

    content = logged_client.get(reverse("workouts:create")).content.decode()

    assert 'value="dumbbell" id="id_equipment_0" checked' in content


def test_sans_materiel_configure_aucune_case_n_est_proposee(logged_client):
    content = logged_client.get(reverse("workouts:create")).content.decode()

    assert 'name="equipment"' not in content


def test_decocher_du_materiel_ecarte_ses_exercices_sans_toucher_la_configuration(
    logged_client, user
):
    """Décocher les haltères à la composition ne doit pas les retirer du profil."""
    UserEquipment.objects.create(user=user, equipment="dumbbell", mode="fixed", weights=[10])

    composer(logged_client, muscles=[], equipment=[])

    workout = Workout.objects.get(user=user)
    assert all(item.exercise.equipment != "dumbbell" for item in workout.items.all())
    assert UserEquipment.objects.filter(user=user, equipment="dumbbell").exists()


def test_un_materiel_coche_reste_utilise(logged_client, user):
    UserEquipment.objects.create(user=user, equipment="dumbbell", mode="fixed", weights=[10])

    composer(logged_client, muscles=[], equipment=["dumbbell"])

    workout = Workout.objects.get(user=user)
    assert workout.items.exists()


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


# --------------------------------------------------------------------------- #
# Ajustement des temps par format (issue #32)
# --------------------------------------------------------------------------- #


def test_le_declencheur_du_format_n_englobe_pas_le_panneau_de_temps(logged_client):
    """Un <summary> imbriqué dans le <label> du radio partage son clic avec lui :
    le panneau « Ajuster les réglages » doit rester hors du <label>."""
    content = logged_client.get(reverse("workouts:create")).content.decode()

    assert '<label class="ugg-format__select">' in content
    assert '<label class="ugg-format">' not in content
    assert '<div class="ugg-format">' in content


def test_le_panneau_de_temps_reste_un_declencheur_independant(logged_client):
    content = logged_client.get(reverse("workouts:create")).content.decode()

    assert content.count('<details class="ugg-format__tune">') == 4
    assert content.count("<summary>Ajuster les réglages</summary>") == 4


# --------------------------------------------------------------------------- #
# Pic de répétitions de la pyramide, réglable (issue #34)
# --------------------------------------------------------------------------- #


def test_le_pic_de_repetitions_n_apparait_que_pour_la_pyramide(logged_client):
    content = logged_client.get(reverse("workouts:create")).content.decode()

    assert content.count("Répétitions au pic") == 1
    assert 'name="reps_pyramid" value="12" min="6" max="20"' in content


def test_un_pic_personnalise_est_transmis_et_enregistre(logged_client, user):
    composer(
        logged_client,
        workout_format=Workout.Format.PYRAMID,
        reps_pyramid="8",
    )

    workout = Workout.objects.get(user=user)
    assert workout.peak_reps == 8
    assert max(workout.items.first().reps) == 8


def test_le_pic_d_un_format_non_retenu_n_empeche_pas_l_envoi(logged_client, user):
    """Régler la pyramide puis composer un Circuit ne doit pas être bloqué par elle."""
    composer(
        logged_client,
        workout_format=Workout.Format.CIRCUIT,
        reps_pyramid="9999",
    )

    assert Workout.objects.filter(user=user).exists()


# --------------------------------------------------------------------------- #
# Durée : paliers de 5 minutes, par défaut 30 (issue #32)
# --------------------------------------------------------------------------- #


def test_la_duree_propose_onze_paliers_de_cinq_en_cinq(logged_client):
    content = logged_client.get(reverse("workouts:create")).content.decode()

    for minutes in range(10, 61, 5):
        assert f'value="{minutes}"' in content


def test_la_duree_par_defaut_est_trente_minutes(logged_client):
    content = logged_client.get(reverse("workouts:create")).content.decode()

    assert 'value="30" id="id_duration_minutes_4" required checked' in content


def test_le_libelle_de_duree_porte_l_unite(logged_client):
    """L'unité n'est plus répétée sur chacun des onze crans (CLAUDE.md § Socle mobile)."""
    content = logged_client.get(reverse("workouts:create")).content.decode()

    assert "Durée (minutes)" in content
    assert "10 min" not in content


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


def test_le_titre_est_le_declencheur_du_renommage(logged_client, user):
    """Un clic sur le titre ouvre le panneau — pas de bouton « Renommer »
    séparé à chercher (issue #44 suite)."""
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert '<details class="ugg-disclosure ugg-disclosure--plain min-w-0 flex-1">' in content
    assert (
        f'<summary><h1 class="ugg-title text-3xl">{workout.display_name}</h1></summary>' in content
    )


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


def test_le_nom_saisi_a_la_creation_est_enregistre(logged_client, user):
    composer(logged_client, name="Jambes du lundi")
    workout = Workout.objects.get(user=user)

    assert workout.name == "Jambes du lundi"
    assert workout.display_name == "Jambes du lundi"


# --------------------------------------------------------------------------- #
# Récupération entre tours/blocs (issue #44 suite)
# --------------------------------------------------------------------------- #


def test_le_formulaire_propose_la_recuperation_par_format(logged_client):
    content = logged_client.get(reverse("workouts:create")).content.decode()

    assert 'name="recovery_circuit"' in content
    assert 'name="recovery_tabata"' in content
    assert 'name="recovery_pyramid"' in content


def test_la_recuperation_saisie_est_enregistree(logged_client, user):
    composer(logged_client, **{"recovery_circuit": "42"})
    workout = Workout.objects.get(user=user)

    assert workout.recovery_seconds == 42


def test_le_repos_entre_les_tours_est_une_regle_graduee(logged_client, user):
    """Six crans de 30 s à 3 min, dans l'encart des exercices — pas un champ
    libre ni un panneau repliable (issue #44 suite)."""
    workout = build_workout(user, Exercise.objects.get(slug="Barbell_Squat"))

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert content.count('name="recovery_seconds"') == len(generator.RECOVERY_RULER_SECONDS)
    for value in generator.RECOVERY_RULER_SECONDS:
        assert f'value="{value}"' in content


def test_le_repos_entre_les_tours_se_modifie(logged_client, user):
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    response = logged_client.post(
        reverse("workouts:recovery", args=[workout.pk]),
        {"recovery_seconds": "90"},
        follow=True,
    )

    workout.refresh_from_db()
    assert response.status_code == 200
    assert workout.recovery_seconds == 90
    assert re.search(r'value="90"\s*checked', response.content.decode())


def test_le_repos_entre_les_tours_est_borne(logged_client, user):
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    logged_client.post(reverse("workouts:recovery", args=[workout.pk]), {"recovery_seconds": "999"})
    workout.refresh_from_db()
    assert workout.recovery_seconds == 180

    logged_client.post(reverse("workouts:recovery", args=[workout.pk]), {"recovery_seconds": "5"})
    workout.refresh_from_db()
    assert workout.recovery_seconds == 30


def test_le_repos_hors_des_crans_retombe_sur_la_valeur_par_defaut_a_l_affichage(
    logged_client, user
):
    """La Pyramide n'a aucune récupération par défaut (0, hors plage) : la
    règle ne doit rien casser, elle affiche un repli sans rien enregistrer."""
    composer(logged_client, workout_format=Workout.Format.PYRAMID)
    workout = Workout.objects.get(user=user)
    assert workout.recovery_seconds == 0

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert re.search(rf'value="{generator.RECOVERY_RULER_DEFAULT}"\s*checked', content)
    workout.refresh_from_db()
    assert workout.recovery_seconds == 0


def test_le_repos_entre_les_tours_refuse_la_methode_get(logged_client, user):
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    response = logged_client.get(reverse("workouts:recovery", args=[workout.pk]))

    assert response.status_code == 405


def test_on_ne_modifie_pas_le_repos_entre_les_tours_d_une_seance_d_un_autre(
    logged_client, staff_client, user
):
    composer(logged_client)
    workout = Workout.objects.get(user=user)

    response = staff_client.post(
        reverse("workouts:recovery", args=[workout.pk]), {"recovery_seconds": "50"}
    )

    workout.refresh_from_db()
    assert response.status_code == 404
    assert workout.recovery_seconds != 50


# --------------------------------------------------------------------------- #
# Rafraîchissement et repos d'un exercice (issue #44)
# --------------------------------------------------------------------------- #


def test_un_exercice_de_seance_se_rafraichit(logged_client, user):
    from exercises.models import Muscle

    squat = Exercise.objects.get(slug="Barbell_Squat")
    bench = Exercise.objects.get(slug="Dumbbell_Bench_Press")
    UserEquipment.objects.create(user=user, equipment="dumbbell", mode="fixed", weights=[10])
    workout = build_workout(user, squat)
    workout.muscles.set(Muscle.objects.filter(slug="chest"))
    item = workout.items.first()

    response = logged_client.post(reverse("workouts:exercise_refresh", args=[workout.pk, item.pk]))

    item.refresh_from_db()
    assert response.status_code == 200
    assert item.exercise_id == bench.pk
    assert f'id="seance-exercice-{item.pk}"' in response.content.decode()


def test_le_rafraichissement_signale_l_absence_d_alternative(logged_client, user):
    from exercises.models import Muscle

    bench = Exercise.objects.get(slug="Dumbbell_Bench_Press")
    UserEquipment.objects.create(user=user, equipment="dumbbell", mode="fixed", weights=[10])
    workout = build_workout(user, bench)
    workout.muscles.set(Muscle.objects.filter(slug="chest"))
    item = workout.items.first()

    response = logged_client.post(reverse("workouts:exercise_refresh", args=[workout.pk, item.pk]))

    item.refresh_from_db()
    assert response.status_code == 200
    assert item.exercise_id == bench.pk
    assert "Aucun autre exercice disponible" in response.content.decode()


def test_le_rafraichissement_refuse_la_methode_get(logged_client, user):
    squat = Exercise.objects.get(slug="Barbell_Squat")
    workout = build_workout(user, squat)
    item = workout.items.first()

    response = logged_client.get(reverse("workouts:exercise_refresh", args=[workout.pk, item.pk]))

    assert response.status_code == 405


def test_on_ne_rafraichit_pas_l_exercice_d_une_seance_d_un_autre(logged_client, staff_client, user):
    squat = Exercise.objects.get(slug="Barbell_Squat")
    workout = build_workout(user, squat)
    item = workout.items.first()

    response = staff_client.post(reverse("workouts:exercise_refresh", args=[workout.pk, item.pk]))

    item.refresh_from_db()
    assert response.status_code == 404
    assert item.exercise_id == squat.pk


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


# --------------------------------------------------------------------------- #
# Rappel d'un exercice (issue #30)
# --------------------------------------------------------------------------- #


def build_workout(user, exercise):
    """Séance à un seul exercice, construite directement — sans passer par le
    générateur — pour savoir précisément quelle fiche sera affichée."""
    workout = Workout.objects.create(
        user=user,
        duration_minutes=Workout.Duration.THIRTY,
        format=Workout.Format.CIRCUIT,
        planned_seconds=600,
    )
    WorkoutExercise.objects.create(
        workout=workout,
        position=1,
        block_index=0,
        block_label="Bloc 1",
        exercise=exercise,
        rounds=3,
        reps=[10, 10, 10],
        rest_seconds=60,
    )
    return workout


def test_un_exercice_documente_se_deplie_dans_la_seance(logged_client, user):
    """Cliquer sur l'exercice doit donner un rappel — consignes et images."""
    squat = Exercise.objects.get(slug="Barbell_Squat")
    workout = build_workout(user, squat)

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert '<details class="ugg-disclosure ugg-disclosure--plain">' in content
    assert "<summary>Barbell Squat</summary>" in content
    assert "Placer la barre sur les trapèzes" in content
    assert 'class="ugg-exercise__gallery' in content
    assert 'class="ugg-lightbox"' in content


def test_un_exercice_sans_documentation_reste_un_simple_texte(logged_client, user):
    """Sans consigne ni image, rien à déplier : pas de repli vide."""
    minimal = Exercise.objects.get(slug="Text_Only_Exercise")
    workout = build_workout(user, minimal)

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert '<p class="font-semibold">Text Only Exercise</p>' in content
    # Le titre de la séance porte lui aussi un disclosure --plain (issue #44
    # suite) : on vérifie l'absence de celui, spécifique, de l'exercice.
    assert '<details class="ugg-disclosure ugg-disclosure--plain">' not in content


def test_le_rappel_privilegie_la_traduction(logged_client, user):
    squat = Exercise.objects.get(slug="Barbell_Squat")
    squat.instructions_fr = ["Consigne traduite en français."]
    squat.save()
    workout = build_workout(user, squat)

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert "Consigne traduite en français." in content
    assert "Placer la barre sur les trapèzes" not in content


def test_le_reste_du_bloc_est_inchange(logged_client, user):
    """Le repli du nom ne doit pas déplacer le matériel ni la charge."""
    squat = Exercise.objects.get(slug="Barbell_Squat")
    workout = build_workout(user, squat)

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert "Barre" in content
    assert "10 · 10 · 10" in content


# --------------------------------------------------------------------------- #
# Traduction unitaire depuis la séance (issue #31)
# --------------------------------------------------------------------------- #


def test_sans_fournisseur_le_bouton_de_traduction_n_apparait_pas(logged_client, user):
    squat = Exercise.objects.get(slug="Barbell_Squat")
    workout = build_workout(user, squat)

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert "Traduire cette fiche" not in content


def test_avec_un_fournisseur_le_bouton_de_traduction_apparait(logged_client, user, monkeypatch):
    stub = type("Stub", (), {"generate": lambda self, prompt, **kwargs: "[]"})()
    monkeypatch.setattr("exercises.views.get_active_client", lambda: stub)
    monkeypatch.setattr("workouts.views.get_active_client", lambda: stub)

    squat = Exercise.objects.get(slug="Barbell_Squat")
    workout = build_workout(user, squat)

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert "Traduire cette fiche" in content
    assert reverse("exercises:translate", args=[squat.pk]) in content


# --------------------------------------------------------------------------- #
# Minuteur de séance (issue #35)
# --------------------------------------------------------------------------- #


def test_le_bouton_lancer_la_seance_apparait(logged_client, user):
    squat = Exercise.objects.get(slug="Barbell_Squat")
    workout = build_workout(user, squat)

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert 'id="lancer-seance"' in content
    assert "Lancer la séance" in content
    assert 'id="minuteur-modal"' in content
    assert "core/js/workout_timer.js" in content


def test_le_deroule_chronometre_est_transmis_en_json(logged_client, user):
    squat = Exercise.objects.get(slug="Barbell_Squat")
    workout = build_workout(user, squat)

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert 'id="minuteur-donnees"' in content
    # Trois rounds de répétitions, un repos entre chacun : six pas.
    assert content.count('"itemId"') == 6


def test_sans_exercice_le_bouton_de_lancement_n_apparait_pas(logged_client, user):
    """Une séance sans exercice ne peut rien chronométrer — le bouton serait mort."""
    workout = Workout.objects.create(
        user=user,
        duration_minutes=Workout.Duration.THIRTY,
        format=Workout.Format.CIRCUIT,
        planned_seconds=0,
    )

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert 'id="lancer-seance"' not in content
    assert 'id="minuteur-modal"' not in content


def test_le_panneau_du_tiers_bas_est_present(logged_client, user):
    """Issue #35 suite : l'exercice en cours se lit en grand au tiers bas de l'écran."""
    squat = Exercise.objects.get(slug="Barbell_Squat")
    workout = build_workout(user, squat)

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert 'id="minuteur-exercice-actuel"' in content
    assert 'id="minuteur-exercice-actuel-photo"' in content
    assert 'id="minuteur-exercice-actuel-nom"' in content
    assert 'id="minuteur-exercice-actuel-materiel"' in content
    assert 'id="minuteur-exercice-actuel-muscles"' in content


def test_la_timeline_porte_le_materiel_et_les_muscles_de_chaque_exercice(logged_client, user):
    """Le panneau du tiers bas relit ces attributs plutôt que de les dupliquer
    dans le JSON du minuteur (voir workout_timer.js)."""
    squat = Exercise.objects.get(slug="Barbell_Squat")
    workout = build_workout(user, squat)

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert f'data-item-id="{workout.items.first().pk}"' in content
    assert 'data-equipment="Barre"' in content
    assert "data-muscles=" in content


def test_la_timeline_porte_toutes_les_photos_d_un_exercice(logged_client, user):
    """Le panneau du tiers bas fait défiler les photos d'un exercice qui en
    compte plusieurs (issue #35 suite) — la timeline transmet la liste
    complète, séparée par « | », pas la seule première photo."""
    squat = Exercise.objects.get(slug="Barbell_Squat")
    assert len(squat.image_urls) == 2
    workout = build_workout(user, squat)

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    expected = "|".join(squat.image_urls)
    assert f'data-photos="{expected}"' in content


def test_la_timeline_ne_porte_aucune_photo_sans_illustration(logged_client, user):
    minimal = Exercise.objects.get(slug="Text_Only_Exercise")
    workout = build_workout(user, minimal)

    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert 'data-photos=""' in content
