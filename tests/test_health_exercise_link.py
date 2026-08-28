from datetime import timedelta

import pytest
from django.utils import timezone

from exercises.models import Exercise
from health.exercise_link import annotate_linked_exercises
from health.models import Activity

pytestmark = pytest.mark.django_db


def _activity(user, activity_type):
    now = timezone.now()
    return Activity.objects.create(
        user=user,
        activity_type=activity_type,
        started_at=now,
        ended_at=now + timedelta(minutes=30),
    )


def _exercise(slug, category=Exercise.Category.CARDIO):
    return Exercise.objects.create(slug=slug, name=slug, category=category, level="beginner")


def test_un_type_cardio_reconnu_est_rapproche_de_sa_fiche(user):
    exercise = _exercise("Running_Treadmill")
    activity = _activity(user, Activity.ActivityType.RUNNING)

    annotate_linked_exercises([activity])

    assert activity.linked_exercise == exercise


def test_un_type_sans_equivalent_dans_le_catalogue_n_est_rien(user):
    # Aucune fiche « Bicycling » créée ici : le rapprochement doit rester
    # None plutôt que planter ou pointer sur une autre fiche.
    activity = _activity(user, Activity.ActivityType.CYCLING)

    annotate_linked_exercises([activity])

    assert activity.linked_exercise is None


def test_musculation_et_autre_ne_sont_jamais_rapproches(user):
    # Trop d'exercices possibles derrière ces deux types pour qu'un seul
    # choix soit fiable (issue #82) — aucune fiche ne doit être proposée,
    # même si une fiche du même nom existait par coïncidence.
    _exercise("Musculation")
    strength = _activity(user, Activity.ActivityType.STRENGTH_TRAINING)
    other = _activity(user, Activity.ActivityType.OTHER)

    annotate_linked_exercises([strength, other])

    assert strength.linked_exercise is None
    assert other.linked_exercise is None


def test_plusieurs_activites_du_meme_type_partagent_la_meme_fiche(user):
    exercise = _exercise("Bicycling")
    first = _activity(user, Activity.ActivityType.CYCLING)
    second = _activity(user, Activity.ActivityType.CYCLING)

    annotate_linked_exercises([first, second])

    assert first.linked_exercise == exercise
    assert second.linked_exercise == exercise
