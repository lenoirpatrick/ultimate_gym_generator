"""Déroulé chronométré du minuteur de séance (issue #35).

`build_timeline` déplie la recette d'une séance (rounds, effort, repos) en pas
d'exécution chronologiques. L'ordre est l'enjeu principal : un circuit ou un
HIIT enchaînent un tour de tous leurs exercices avant de le répéter, un
Tabata ou une pyramide épuisent un exercice avant de passer au suivant.
"""

import random

import pytest

from workouts import generator, timer
from workouts.models import Workout

pytestmark = pytest.mark.django_db


@pytest.fixture
def rng():
    return random.Random(1789)


def composer(user, rng, **overrides) -> Workout:
    params = {
        "duration_minutes": 20,
        "workout_format": Workout.Format.CIRCUIT,
        "muscles": [],
        "favorites_ratio": 0,
    }
    return generator.generate(user=user, rng=rng, **(params | overrides))


def test_une_seance_sans_exercice_ne_produit_aucun_pas(user):
    workout = Workout.objects.create(user=user, duration_minutes=20, format=Workout.Format.CIRCUIT)

    assert timer.build_timeline(workout) == []


def test_le_tabata_epuise_un_exercice_avant_le_suivant(user, rng):
    """Huit rounds d'effort/repos pour le premier bloc, avant que le second n'apparaisse."""
    workout = composer(user, rng, workout_format=Workout.Format.TABATA, duration_minutes=20)
    items = list(workout.items.all())
    assert len(items) > 1, "il faut au moins deux blocs pour vérifier l'ordre"

    steps = timer.build_timeline(workout)
    first_item_id = items[0].pk

    # Les 16 premiers pas (8 rounds x effort/repos) appartiennent tous au
    # premier exercice : aucun autre bloc ne s'intercale.
    first_block_steps = steps[:16]
    assert all(step["itemId"] == first_item_id for step in first_block_steps)
    assert steps[16]["itemId"] == items[1].pk


def test_le_tabata_alterne_effort_et_repos(user, rng):
    workout = composer(user, rng, workout_format=Workout.Format.TABATA, duration_minutes=20)
    steps = timer.build_timeline(workout)

    phases = [step["phase"] for step in steps[:16]]
    assert phases == ["work", "rest"] * 8
    assert steps[0]["seconds"] == 20
    assert steps[1]["seconds"] == 10


def test_le_circuit_enchaine_un_tour_avant_de_le_repeter(user, rng):
    """Round-robin : le tour 1 passe par chaque exercice avant que le tour 2 ne commence."""
    workout = composer(user, rng, workout_format=Workout.Format.CIRCUIT, duration_minutes=20)
    items = list(workout.items.all())
    assert len(items) > 1

    steps = timer.build_timeline(workout)
    steps_per_lap = len(items) * 2  # effort + repos par exercice

    first_lap_ids = [step["itemId"] for step in steps[:steps_per_lap:2]]
    assert first_lap_ids == [item.pk for item in items]

    second_lap_ids = [step["itemId"] for step in steps[steps_per_lap : 2 * steps_per_lap : 2]]
    assert second_lap_ids == [item.pk for item in items]


def test_le_circuit_numerote_les_tours(user, rng):
    workout = composer(user, rng, workout_format=Workout.Format.CIRCUIT, duration_minutes=20)
    items = list(workout.items.all())
    steps = timer.build_timeline(workout)
    steps_per_lap = len(items) * 2

    assert steps[0]["lap"] == 1
    assert steps[steps_per_lap]["lap"] == 2
    assert steps[0]["totalLaps"] == steps[steps_per_lap]["totalLaps"]


def test_la_pyramide_decompte_en_repetitions_pas_en_secondes(user, rng):
    workout = composer(
        user, rng, workout_format=Workout.Format.PYRAMID, duration_minutes=20, peak_reps=12
    )
    item = workout.items.first()
    steps = timer.build_timeline(workout)

    work_steps = [step for step in steps if step["itemId"] == item.pk and step["phase"] == "work"]
    assert [step["seconds"] for step in work_steps] == [None] * len(work_steps)
    assert [step["reps"] for step in work_steps] == item.reps


def test_la_pyramide_epuise_un_exercice_avant_le_suivant(user, rng):
    workout = composer(
        user, rng, workout_format=Workout.Format.PYRAMID, duration_minutes=40, peak_reps=12
    )
    items = list(workout.items.all())
    if len(items) < 2:
        pytest.skip("séance trop courte pour composer plus d'une pyramide")

    steps = timer.build_timeline(workout)
    first_item = items[0]
    # Un pas d'effort par round, plus un pas de repos si le format en prévoit un.
    steps_for_first_item = len(first_item.reps) * (2 if first_item.rest_seconds else 1)

    assert all(step["itemId"] == first_item.pk for step in steps[:steps_for_first_item])
    assert steps[steps_for_first_item]["itemId"] == items[1].pk


def test_un_pas_de_repos_absent_si_le_repos_est_nul(user, rng):
    workout = composer(
        user,
        rng,
        workout_format=Workout.Format.CIRCUIT,
        duration_minutes=20,
        rest_seconds=0,
    )
    steps = timer.build_timeline(workout)

    assert all(step["phase"] == "work" for step in steps)
