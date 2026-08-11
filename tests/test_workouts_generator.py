"""Générateur de séances : minutage, sélection, charges.

Le minutage est de l'arithmétique stricte : un Tabata annoncé 4 minutes par bloc
dure 4 minutes. C'est ce que ces tests vérifient d'abord.
"""

import random
from decimal import Decimal

import pytest

from accounts.models import UserEquipment
from exercises.models import Exercise, Favorite, Muscle
from workouts import generator
from workouts.models import Workout, WorkoutExercise

pytestmark = pytest.mark.django_db

DURATIONS = [choice[0] for choice in Workout.Duration.choices]
FORMATS = [choice[0] for choice in Workout.Format.choices]


@pytest.fixture
def rng():
    """Tirage reproductible : un test de sélection ne doit pas dépendre du hasard."""
    return random.Random(1789)


@pytest.fixture
def halteres(user):
    return UserEquipment.objects.create(
        user=user,
        equipment="dumbbell",
        mode=UserEquipment.Mode.ADJUSTABLE,
        min_kg=Decimal("2"),
        max_kg=Decimal("20"),
        step_kg=Decimal("2"),
    )


def composer(user, rng, **overrides) -> Workout:
    params = {
        "duration_minutes": 20,
        "workout_format": Workout.Format.CIRCUIT,
        "muscles": [],
        "favorites_ratio": 0,
    }
    return generator.generate(user=user, rng=rng, **(params | overrides))


# --------------------------------------------------------------------------- #
# Minutage
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("duration", DURATIONS)
@pytest.mark.parametrize("workout_format", FORMATS)
def test_une_seance_ne_depasse_jamais_la_duree_demandee(duration, workout_format):
    """Vingt-quatre combinaisons : aucune ne doit déborder du temps disponible."""
    blueprint = generator.build_blueprint(workout_format, duration)

    assert blueprint.total_seconds <= duration * 60


@pytest.mark.parametrize("duration", DURATIONS)
@pytest.mark.parametrize("workout_format", FORMATS)
def test_une_seance_occupe_l_essentiel_du_temps(duration, workout_format):
    """Une séance de 60 min qui n'en remplit que 30 n'a pas rendu le service demandé."""
    blueprint = generator.build_blueprint(workout_format, duration)

    assert blueprint.total_seconds >= duration * 60 * 0.75


@pytest.mark.parametrize("duration", DURATIONS)
@pytest.mark.parametrize("workout_format", FORMATS)
def test_une_seance_contient_toujours_au_moins_un_exercice(duration, workout_format):
    blueprint = generator.build_blueprint(workout_format, duration)

    assert blueprint.needed >= 1
    assert blueprint.slots


def test_un_bloc_tabata_dure_exactement_quatre_minutes():
    blueprint = generator.build_blueprint(Workout.Format.TABATA, 20)
    item = blueprint.slots[0]

    assert (item.work_seconds, item.rest_seconds, item.rounds) == (20, 10, 8)
    assert item.rounds * (item.work_seconds + item.rest_seconds) == 240


def test_tabata_de_vingt_minutes_donne_quatre_blocs():
    """4 blocs de 4 min et 3 récupérations d'une minute : 19 minutes."""
    blueprint = generator.build_blueprint(Workout.Format.TABATA, 20)

    assert blueprint.needed == 4
    assert blueprint.total_seconds == 4 * 240 + 3 * 60


def test_un_circuit_repete_les_memes_exercices_a_chaque_tour():
    blueprint = generator.build_blueprint(Workout.Format.CIRCUIT, 30)

    rangs = [slot.exercise_rank for slot in blueprint.slots]
    assert rangs == sorted(set(rangs))
    assert all(slot.rounds == blueprint.slots[0].rounds for slot in blueprint.slots)
    assert blueprint.slots[0].rounds > 1


@pytest.mark.parametrize("duration", DURATIONS)
def test_une_pyramide_est_toujours_symetrique(duration):
    blueprint = generator.build_blueprint(Workout.Format.PYRAMID, duration)
    reps = blueprint.slots[0].reps

    assert reps == reps[::-1]
    assert reps[len(reps) // 2] == min(reps)


def test_la_pyramide_complete_est_retenue_des_qu_elle_tient():
    """Elle ne rentre pas dans dix minutes ; à quinze, elle remplit assez pour l'emporter."""
    breve = generator.build_blueprint(Workout.Format.PYRAMID, 10)
    longue = generator.build_blueprint(Workout.Format.PYRAMID, 15)

    assert breve.slots[0].reps == [10, 8, 6, 8, 10]
    assert breve.total_seconds <= 600
    assert longue.slots[0].reps == [12, 10, 8, 6, 8, 10, 12]


@pytest.mark.parametrize("duration", DURATIONS)
def test_la_pyramide_ne_se_rabat_pas_sur_la_forme_la_plus_courte(duration):
    """Viser le seul remplissage retiendrait toujours 8-6-8, qui se divise mieux."""
    blueprint = generator.build_blueprint(Workout.Format.PYRAMID, duration)

    assert len(blueprint.slots[0].reps) >= 5


def test_un_format_inconnu_est_refuse():
    with pytest.raises(generator.GenerationError, match="Type de travail inconnu"):
        generator.build_blueprint("zumba", 20)


# --------------------------------------------------------------------------- #
# Pic de répétitions de la pyramide, réglable (issue #34)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("peak", [6, 7, 8, 10, 11, 12, 20])
def test_une_pyramide_reglee_reste_symetrique_quel_que_soit_le_pic(peak):
    """Un pic impair (7, 11) ne doit ni casser la symétrie ni sauter le plancher."""
    shape = generator._pyramid_shape(peak)

    assert shape == shape[::-1]
    assert min(shape) == generator.PYRAMID_FLOOR_REPS
    assert max(shape) == peak


def test_le_pic_par_defaut_est_douze():
    blueprint = generator.build_blueprint(Workout.Format.PYRAMID, 15)

    assert max(blueprint.slots[0].reps) == 12


def test_un_pic_personnalise_remplace_le_defaut():
    blueprint = generator.build_blueprint(Workout.Format.PYRAMID, 15, peak_reps=8)

    assert blueprint.slots[0].reps == [8, 6, 8]


def test_un_pic_hors_bornes_est_borne():
    trop_bas = generator.build_blueprint(Workout.Format.PYRAMID, 15, peak_reps=1)
    trop_haut = generator.build_blueprint(Workout.Format.PYRAMID, 60, peak_reps=999)

    assert min(trop_bas.slots[0].reps) == generator.MIN_PYRAMID_PEAK
    assert max(trop_bas.slots[0].reps) == generator.MIN_PYRAMID_PEAK
    assert max(trop_haut.slots[0].reps) == generator.MAX_PYRAMID_PEAK


def test_un_pic_plus_bas_laisse_de_la_place_pour_plus_d_exercices():
    """C'est l'algorithme d'adaptation demandé par l'issue #34 : une pyramide
    plus courte doit libérer du temps pour répéter le mouvement plus souvent."""
    haut = generator.build_blueprint(Workout.Format.PYRAMID, 20, peak_reps=20)
    bas = generator.build_blueprint(Workout.Format.PYRAMID, 20, peak_reps=6)

    assert bas.needed >= haut.needed


def test_le_pic_ne_concerne_que_la_pyramide():
    """Un pic transmis à un autre format ne doit provoquer ni erreur ni effet."""
    blueprint = generator.build_blueprint(Workout.Format.TABATA, 20, peak_reps=8)

    assert blueprint.slots[0].reps == []


# --------------------------------------------------------------------------- #
# Temps personnalisés (issue #26)
# --------------------------------------------------------------------------- #


def test_les_temps_personnalises_remplacent_ceux_du_format():
    blueprint = generator.build_blueprint(
        Workout.Format.TABATA, 20, work_seconds=30, rest_seconds=15
    )
    item = blueprint.slots[0]

    assert (item.work_seconds, item.rest_seconds) == (30, 15)


def test_la_pyramide_n_expose_que_le_repos():
    """Elle se compte en répétitions : lui fournir un effort n'a pas de sens."""
    blueprint = generator.build_blueprint(
        Workout.Format.PYRAMID, 15, work_seconds=99, rest_seconds=30
    )

    assert blueprint.slots[0].rest_seconds == 30
    assert blueprint.slots[0].work_seconds is None


@pytest.mark.parametrize(
    ("work_seconds", "rest_seconds", "expected_work", "expected_rest"),
    [
        (1, 500, generator.MIN_WORK_SECONDS, generator.MAX_REST_SECONDS),
        (500, -5, generator.MAX_WORK_SECONDS, generator.MIN_REST_SECONDS),
    ],
)
def test_les_temps_personnalises_sont_bornes(
    work_seconds, rest_seconds, expected_work, expected_rest
):
    """Un formulaire mal rempli ne doit pas produire une séance absurde."""
    blueprint = generator.build_blueprint(
        Workout.Format.HIIT, 20, work_seconds=work_seconds, rest_seconds=rest_seconds
    )

    assert blueprint.slots[0].work_seconds == expected_work
    assert blueprint.slots[0].rest_seconds == expected_rest


def test_sans_reglage_les_temps_par_defaut_du_format_restent_inchanges():
    """Non-régression : un Tabata sans réglage reste 20 s / 10 s, 4 min par bloc."""
    blueprint = generator.build_blueprint(Workout.Format.TABATA, 20)
    item = blueprint.slots[0]

    assert (item.work_seconds, item.rest_seconds, item.rounds) == (20, 10, 8)


# --------------------------------------------------------------------------- #
# Récupération entre tours/blocs (issue #44 suite)
# --------------------------------------------------------------------------- #
#
# Distincte du repos entre exercices (rest_seconds, ci-dessus) : elle sépare
# deux tours de circuit/HIIT, ou deux blocs de Tabata/Pyramide — voir
# workouts.timer.build_timeline pour son insertion dans le déroulé chronométré.


def test_la_recuperation_par_defaut_suit_le_format():
    blueprint = generator.build_blueprint(Workout.Format.CIRCUIT, 20)

    assert blueprint.recovery_seconds == generator.FORMAT_PERIODS[Workout.Format.CIRCUIT].recovery


def test_une_recuperation_personnalisee_remplace_celle_du_format():
    blueprint = generator.build_blueprint(Workout.Format.TABATA, 20, recovery_seconds=45)

    assert blueprint.recovery_seconds == 45


def test_une_recuperation_hors_bornes_est_bornee():
    trop_haute = generator.build_blueprint(Workout.Format.HIIT, 20, recovery_seconds=999)
    trop_basse = generator.build_blueprint(Workout.Format.HIIT, 20, recovery_seconds=-5)

    assert trop_haute.recovery_seconds == generator.MAX_RECOVERY_SECONDS
    assert trop_basse.recovery_seconds == generator.MIN_RECOVERY_SECONDS


def test_la_pyramide_resout_aussi_une_recuperation():
    """Sans effet sur son propre minutage (aucun terme de récupération dans
    `_pyramid`), mais résolue quand même : le minuteur en a besoin."""
    blueprint = generator.build_blueprint(Workout.Format.PYRAMID, 20, recovery_seconds=20)

    assert blueprint.recovery_seconds == 20


def test_generate_enregistre_la_recuperation_resolue(user, rng):
    par_defaut = composer(user, rng, workout_format=Workout.Format.CIRCUIT)
    personnalisee = composer(user, rng, workout_format=Workout.Format.CIRCUIT, recovery_seconds=42)

    assert par_defaut.recovery_seconds == generator.FORMAT_PERIODS[Workout.Format.CIRCUIT].recovery
    assert personnalisee.recovery_seconds == 42


# --------------------------------------------------------------------------- #
# Sélection des exercices
# --------------------------------------------------------------------------- #


def test_seul_le_poids_du_corps_est_retenu_sans_materiel_declare(user):
    """Rien n'est déclaré : proposer un développé à la barre serait absurde."""
    retenus = generator.eligible_exercises(user, [])

    assert {e.equipment for e in retenus} <= {"body only", ""}


def test_le_materiel_declare_ouvre_les_exercices_correspondants(user, halteres):
    retenus = generator.eligible_exercises(user, [])

    assert "dumbbell" in {e.equipment for e in retenus}


def test_les_etirements_sont_ecartes(user, halteres):
    """Un étirement n'est pas un temps de travail."""
    retenus = generator.eligible_exercises(user, [])

    assert Exercise.Category.STRETCHING not in {e.category for e in retenus}


def test_les_muscles_demandes_restreignent_la_selection(user, halteres):
    retenus = generator.eligible_exercises(user, ["chest"])

    assert [e.slug for e in retenus] == ["Dumbbell_Bench_Press"]


def test_la_seance_echoue_avec_un_message_actionnable(user):
    """Aucun exercice possible : il faut dire quoi changer, pas planter."""
    with pytest.raises(generator.GenerationError, match="Élargis la sélection"):
        generator.generate(
            user=user,
            duration_minutes=20,
            workout_format=Workout.Format.CIRCUIT,
            muscles=["neck"],
            favorites_ratio=0,
        )


def test_la_part_de_favoris_est_respectee(user, halteres, rng):
    """Cent pour cent de favoris : la séance ne doit contenir qu'eux."""
    squat = Exercise.objects.get(slug="Barbell_Squat")
    UserEquipment.objects.create(user=user, equipment="barbell", mode="bodyweight")
    Favorite.objects.create(user=user, exercise=squat)

    choisis = generator.select_exercises(user, [], needed=1, ratio=100, rng=rng)

    assert [e.slug for e in choisis] == ["Barbell_Squat"]


def test_une_part_nulle_n_exclut_pas_les_favoris_du_catalogue(user, halteres, rng):
    """Zéro favori demandé ne veut pas dire « bannir » : le tirage reste ouvert."""
    press = Exercise.objects.get(slug="Dumbbell_Bench_Press")
    Favorite.objects.create(user=user, exercise=press)

    choisis = generator.select_exercises(user, [], needed=2, ratio=0, rng=rng)

    assert len(choisis) == 2


def test_les_favoris_manquants_sont_completes_par_le_catalogue(user, halteres, rng):
    """Demander 100 % de favoris sans en avoir ne doit pas produire une séance vide."""
    choisis = generator.select_exercises(user, [], needed=2, ratio=100, rng=rng)

    assert len(choisis) == 2


def test_un_catalogue_trop_pauvre_fait_tourner_les_memes_exercices(user, rng):
    """Mieux vaut repasser sur les mêmes mouvements que d'écourter la séance."""
    choisis = generator.select_exercises(user, [], needed=8, rng=rng, ratio=0)

    assert len(choisis) == 8
    assert len(set(choisis)) < 8


# --------------------------------------------------------------------------- #
# Matériel retenu pour la séance (issue #32)
# --------------------------------------------------------------------------- #


def test_sans_restriction_tout_le_materiel_configure_est_retenu(user, halteres):
    """`equipment=None` doit se comporter comme avant l'option — aucune restriction."""
    retenus = generator.eligible_exercises(user, [], equipment=None)

    assert "dumbbell" in {e.equipment for e in retenus}


def test_le_materiel_decoche_est_ecarte_de_la_seance(user, halteres):
    """Décocher les haltères dans le formulaire ne doit proposer aucun exercice à haltères."""
    retenus = generator.eligible_exercises(user, [], equipment=[])

    assert {e.equipment for e in retenus} <= {"body only", ""}


def test_le_poids_du_corps_reste_disponible_meme_ecarte(user, halteres):
    """Le poids du corps ne se déclare pas : `equipment=[]` ne peut pas le retirer."""
    retenus = generator.eligible_exercises(user, [], equipment=[])

    assert any(e.equipment in ("body only", "") for e in retenus)


def test_un_materiel_non_configure_ne_peut_pas_etre_ajoute(user):
    """La liste transmise n'est qu'un filtre : elle ne peut pas accorder un matériel
    absent de la configuration réelle de l'utilisateur."""
    retenus = generator.eligible_exercises(user, [], equipment=["dumbbell"])

    assert "dumbbell" not in {e.equipment for e in retenus}


def test_la_restriction_de_materiel_s_applique_aux_charges(user, halteres):
    assert generator.load_options(user, equipment=["dumbbell"])
    assert generator.load_options(user, equipment=[]) == {}


def test_generate_transmet_la_restriction_de_materiel(user, halteres, rng):
    """Intégration bout en bout : composer une séance sans les haltères cochés
    ne doit produire aucun exercice à haltères."""
    workout = generator.generate(
        user=user,
        duration_minutes=20,
        workout_format=Workout.Format.CIRCUIT,
        muscles=[],
        favorites_ratio=0,
        equipment=[],
        rng=rng,
    )

    equipements = {item.exercise.equipment for item in workout.items.all()}
    assert equipements <= {"body only", ""}


# --------------------------------------------------------------------------- #
# Charges
# --------------------------------------------------------------------------- #


def test_aucune_charge_n_est_proposee_sans_materiel(user, rng):
    workout = composer(user, rng)

    assert all(item.loads == [] for item in workout.items.all())


def test_les_charges_viennent_des_crans_declares(user, halteres, rng):
    workout = composer(user, rng, muscles=["chest"])
    crans = [float(load) for load in halteres.available_loads()]

    charges = [load for item in workout.items.all() for load in item.loads]
    assert charges
    assert all(load in crans for load in charges)


def test_un_exercice_plus_exigeant_recoit_une_charge_plus_lourde(user, halteres):
    options = generator.load_options(user)
    debutant = Exercise(equipment="dumbbell", level=Exercise.Level.BEGINNER)
    confirme = Exercise(equipment="dumbbell", level=Exercise.Level.EXPERT)

    assert generator._pick_load(debutant, options) < generator._pick_load(confirme, options)


def test_la_pyramide_alourdit_quand_les_repetitions_baissent(user, halteres, rng):
    workout = composer(user, rng, workout_format=Workout.Format.PYRAMID, muscles=["chest"])
    item = workout.items.first()

    assert len(item.loads) == len(item.reps)
    # La série la plus courte (6 répétitions) doit être la plus lourde.
    plus_courte = item.reps.index(min(item.reps))
    assert item.loads[plus_courte] == max(item.loads)


def test_la_charge_reste_constante_hors_pyramide(user, halteres, rng):
    workout = composer(user, rng, workout_format=Workout.Format.TABATA, muscles=["chest"])

    assert all(len(item.loads) <= 1 for item in workout.items.all())


# --------------------------------------------------------------------------- #
# Séance enregistrée
# --------------------------------------------------------------------------- #


def test_la_seance_est_enregistree_avec_ses_parametres(user, halteres, rng):
    workout = composer(user, rng, duration_minutes=30, muscles=["chest"], favorites_ratio=50)

    assert workout.pk is not None
    assert workout.duration_minutes == 30
    assert workout.favorites_ratio == 50
    assert [m.slug for m in workout.muscles.all()] == ["chest"]


def test_les_temps_demandes_sont_enregistres_sur_la_seance(user, rng):
    """Une séance rouverte doit dire avec quels réglages elle a été composée."""
    workout = composer(
        user, rng, workout_format=Workout.Format.HIIT, work_seconds=30, rest_seconds=30
    )

    assert (workout.work_seconds, workout.rest_seconds) == (30, 30)
    assert workout.items.first().work_seconds == 30


def test_le_deroule_est_ordonne_et_groupe(user, halteres, rng):
    workout = composer(user, rng, workout_format=Workout.Format.TABATA)

    positions = [item.position for item in workout.items.all()]
    assert positions == sorted(positions)

    blocs = workout.blocks()
    assert len(blocs) == len(positions)
    assert blocs[0]["label"] == "Bloc 1"


def test_la_duree_planifiee_est_conservee(user, rng):
    workout = composer(user, rng, duration_minutes=20, workout_format=Workout.Format.TABATA)

    assert workout.planned_seconds == 4 * 240 + 3 * 60
    assert workout.planned_minutes == 19


def test_generate_enregistre_le_nom_fourni(user, rng):
    workout = composer(user, rng, name="Jambes du lundi")

    assert workout.name == "Jambes du lundi"


def test_generate_sans_nom_laisse_le_champ_vide(user, rng):
    workout = composer(user, rng)

    assert workout.name == ""


# --------------------------------------------------------------------------- #
# Rafraîchissement d'un exercice (issue #44)
# --------------------------------------------------------------------------- #
#
# Le catalogue de test (tests/fixtures/exercises.json) ne compte que quatre
# fiches : Barbell Squat (barbell, quadriceps), Calf Stretch (étirement, donc
# toujours écarté), Dumbbell Bench Press (dumbbell, chest) et Text Only
# Exercise (sans matériel ni muscle, donc toujours éligible). Cibler le muscle
# « chest » isole ainsi Dumbbell Bench Press comme seul candidat possible —
# de quoi construire des scénarios déterministes sans mock.


def _item(workout, exercise, **overrides):
    fields = {
        "position": workout.items.count() + 1,
        "block_index": 0,
        "block_label": "Bloc 1",
        "rounds": 3,
        "rest_seconds": 60,
    }
    return WorkoutExercise.objects.create(
        workout=workout, exercise=exercise, **(fields | overrides)
    )


def _workout(user, muscles: list[str] = ()) -> Workout:
    workout = Workout.objects.create(
        user=user,
        duration_minutes=Workout.Duration.THIRTY,
        format=Workout.Format.CIRCUIT,
        planned_seconds=600,
    )
    if muscles:
        workout.muscles.set(Muscle.objects.filter(slug__in=muscles))
    return workout


def test_refresh_exercise_remplace_l_exercice(user, halteres, rng):
    squat = Exercise.objects.get(name="Barbell Squat")
    workout = _workout(user)
    item = _item(workout, squat)

    exercise = generator.refresh_exercise(item, rng)

    assert item.exercise_id == exercise.pk
    assert item.exercise_id != squat.pk


def test_refresh_exercise_conserve_le_creneau(user, halteres, rng):
    squat = Exercise.objects.get(name="Barbell Squat")
    workout = _workout(user)
    item = _item(
        workout, squat, position=1, block_index=2, block_label="Bloc 3", rounds=5, rest_seconds=45
    )
    creneau = (item.position, item.block_index, item.block_label, item.rounds, item.rest_seconds)

    generator.refresh_exercise(item, rng)

    assert (
        item.position,
        item.block_index,
        item.block_label,
        item.rounds,
        item.rest_seconds,
    ) == creneau


def test_refresh_exercise_recalcule_la_charge(user, halteres, rng):
    squat = Exercise.objects.get(name="Barbell Squat")
    bench = Exercise.objects.get(name="Dumbbell Bench Press")
    workout = _workout(user, muscles=["chest"])
    item = _item(workout, squat)

    generator.refresh_exercise(item, rng)

    assert item.exercise_id == bench.pk
    assert item.loads
    assert Decimal(str(item.loads[0])) in halteres.available_loads()


def test_refresh_exercise_evite_les_doublons_du_deroule(user, halteres, rng):
    squat = Exercise.objects.get(name="Barbell Squat")
    bench = Exercise.objects.get(name="Dumbbell Bench Press")
    text_only = Exercise.objects.get(name="Text Only Exercise")
    workout = _workout(user)
    item = _item(workout, squat)
    _item(workout, bench)  # déjà utilisé ailleurs dans le déroulé

    generator.refresh_exercise(item, rng)

    assert item.exercise_id == text_only.pk


def test_refresh_exercise_autorise_un_doublon_si_necessaire(user, rng):
    """Sans matériel déclaré, seul Text Only Exercise est éligible : le
    rafraîchissement doit réussir même si l'unique candidat est déjà utilisé."""
    squat = Exercise.objects.get(name="Barbell Squat")
    text_only = Exercise.objects.get(name="Text Only Exercise")
    workout = _workout(user)
    item = _item(workout, squat)
    _item(workout, text_only)  # seul exercice éligible, déjà pris

    exercise = generator.refresh_exercise(item, rng)

    assert exercise.pk == text_only.pk
    assert item.exercise_id == text_only.pk


def test_refresh_exercise_echoue_sans_alternative(user, halteres, rng):
    """Le muscle ciblé n'a qu'un seul exercice éligible : l'exclure (c'est
    justement celui qu'on rafraîchit) ne laisse plus rien pour le remplacer."""
    bench = Exercise.objects.get(name="Dumbbell Bench Press")
    workout = _workout(user, muscles=["chest"])
    item = _item(workout, bench)

    with pytest.raises(generator.GenerationError):
        generator.refresh_exercise(item, rng)

    assert item.exercise_id == bench.pk
