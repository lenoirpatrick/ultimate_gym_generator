"""Plafond bas : ni sauts, ni charges au-dessus de la tête, ni barre (issue #131).

Un choix de séance, pas de compte : on ne s'entraîne pas toujours au même endroit.
"""

import json
import random
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from exercises.catalog import LOW_CEILING_EXCLUDED
from exercises.models import Exercise, Muscle
from workouts import generator
from workouts.models import Workout, WorkoutExercise

pytestmark = pytest.mark.django_db


@pytest.fixture
def tractions():
    """Exercice au poids du corps de la liste : aucun matériel ne l'écarte par ailleurs."""
    exercise = Exercise.objects.create(
        slug="Pullups",
        name="Pullups",
        category=Exercise.Category.STRENGTH,
        level=Exercise.Level.BEGINNER,
        equipment=Exercise.Equipment.BODY_ONLY,
    )
    exercise.primary_muscles.set(Muscle.objects.filter(slug="lats"))
    return exercise


def test_chaque_exercice_ecarte_existe_dans_le_catalogue_livre():
    """Un identifiant mal recopié n'écarterait rien, silencieusement."""
    shipped = json.loads(
        (Path(settings.BASE_DIR) / "src" / "exercises.json").read_text(encoding="utf-8")
    )

    missing = LOW_CEILING_EXCLUDED - {entry["id"] for entry in shipped}

    assert not missing


def test_sans_plafond_bas_les_tractions_restent_proposees(user, tractions):
    assert tractions in generator.eligible_exercises(user, [])


def test_le_plafond_bas_ecarte_les_exercices_de_la_liste(user, tractions):
    retenus = generator.eligible_exercises(user, [], low_ceiling=True)

    assert tractions not in retenus
    assert retenus.exists()


def test_la_seance_garde_son_choix_de_plafond_bas(user):
    workout = generator.generate(
        user=user,
        duration_minutes=20,
        workout_format=Workout.Format.CIRCUIT,
        muscles=[],
        low_ceiling=True,
        rng=random.Random(1789),
    )

    assert workout.low_ceiling is True
    assert not workout.items.filter(exercise__slug__in=LOW_CEILING_EXCLUDED).exists()


def test_changer_l_exercice_respecte_le_plafond_bas(user, tractions):
    """Le remplaçant obéit à la contrainte de la séance, même composée plus tôt."""
    workout = Workout.objects.create(
        user=user,
        duration_minutes=Workout.Duration.THIRTY,
        format=Workout.Format.CIRCUIT,
        planned_seconds=600,
        low_ceiling=True,
    )
    workout.muscles.set(Muscle.objects.filter(slug="lats"))
    item = WorkoutExercise.objects.create(
        workout=workout,
        position=1,
        block_index=0,
        block_label="Bloc 1",
        exercise=Exercise.objects.get(slug="Barbell_Squat"),
        rounds=3,
        reps=[10, 10, 10],
        rest_seconds=60,
    )

    with pytest.raises(generator.GenerationError):
        generator.refresh_exercise(item, rng=random.Random(1789))


def test_le_formulaire_propose_le_plafond_bas(logged_client):
    content = logged_client.get(reverse("workouts:create")).content.decode()

    assert 'name="low_ceiling"' in content
    assert "Plafond bas" in content


def test_le_plafond_bas_se_choisit_a_la_composition(logged_client, user):
    payload = {
        "duration_minutes": "20",
        "workout_format": Workout.Format.CIRCUIT,
        "favorites_ratio": "25",
        "low_ceiling": "on",
    }

    logged_client.post(reverse("workouts:create"), payload)

    workout = Workout.objects.get(user=user)
    assert workout.low_ceiling is True
    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()
    assert "Plafond bas" in content


def test_le_plafond_bas_est_decoche_par_defaut(logged_client, user):
    payload = {
        "duration_minutes": "20",
        "workout_format": Workout.Format.CIRCUIT,
        "favorites_ratio": "25",
    }

    logged_client.post(reverse("workouts:create"), payload)

    assert Workout.objects.get(user=user).low_ceiling is False
