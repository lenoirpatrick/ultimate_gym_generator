"""Générateur de séances : minutage, sélection, charges.

Le minutage est de l'arithmétique stricte : un Tabata annoncé 4 minutes par bloc
dure 4 minutes. C'est ce que ces tests vérifient d'abord.
"""

import random
from decimal import Decimal

import pytest

from accounts.models import UserEquipment
from exercises.models import Exercise, Favorite
from workouts import generator
from workouts.models import Workout

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
