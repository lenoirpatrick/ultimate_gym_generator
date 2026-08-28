"""Rapprochement entre une activité et sa fiche du catalogue (issue #82).

Seuls les types cardio ayant un exercice équivalent univoque dans le
catalogue (`exercises.Exercise`, livré par free-exercise-db) sont rapprochés.
`strength_training`/`other` recouvrent chacun des dizaines d'exercices
possibles — aucun choix unique n'y serait fiable — et `swimming`/`hiking`/
`yoga` n'ont tout simplement aucun équivalent dans ce catalogue : plutôt
qu'un rapprochement hasardeux, ces types n'affichent rien.
"""

from exercises.models import Exercise

from .models import Activity

_EXERCISE_SLUG_BY_ACTIVITY_TYPE: dict[str, str] = {
    Activity.ActivityType.RUNNING: "Running_Treadmill",
    Activity.ActivityType.WALKING: "Walking_Treadmill",
    Activity.ActivityType.CYCLING: "Bicycling",
    Activity.ActivityType.ROWING: "Rowing_Stationary",
    Activity.ActivityType.ELLIPTICAL: "Elliptical_Trainer",
}


def annotate_linked_exercises(activities) -> None:
    """Pose `activity.linked_exercise` sur chaque activité (même mécanique
    que `workouts.views._annotate_favorites` — attribut posé à la volée
    plutôt qu'un `annotate()` de requête, le rapprochement n'étant pas une
    colonne de la base). `None` si le type n'a pas d'équivalent fiable.
    """
    exercises_by_slug = {
        exercise.slug: exercise
        for exercise in Exercise.objects.filter(slug__in=_EXERCISE_SLUG_BY_ACTIVITY_TYPE.values())
    }
    for activity in activities:
        slug = _EXERCISE_SLUG_BY_ACTIVITY_TYPE.get(activity.activity_type)
        activity.linked_exercise = exercises_by_slug.get(slug) if slug else None
