"""Minutage d'exécution d'une séance, pour le minuteur de suivi (issue #35).

Un `Workout` mémorise sa recette (rounds, effort, repos par exercice), pas son
déroulé chronologique. `build_timeline` la déplie en pas d'exécution, dans
l'ordre où ils se jouent réellement à la salle : un Circuit ou un HIIT
partagent un seul bloc pour plusieurs exercices — un tour les enchaîne tous
avant de le répéter (round-robin). Un Tabata ou une Pyramide n'ont qu'un
exercice par bloc : ses rounds s'épuisent avant de passer au suivant, l'ordre
des items suffit déjà.
"""

from dataclasses import dataclass

from .models import Workout, WorkoutExercise

INTERLEAVED_FORMATS = (Workout.Format.HIIT, Workout.Format.CIRCUIT)


@dataclass(frozen=True)
class TimerStep:
    """Un pas du déroulé chronométré : un effort, ou le repos qui le suit.

    `seconds` vaut `None` pour un effort en répétitions (pyramide) : sa durée
    dépend de l'utilisateur, pas d'un chronomètre — le minuteur attend alors
    une confirmation manuelle plutôt que de décompter.
    """

    item_id: int
    phase: str
    seconds: int | None
    reps: int | None
    lap: int
    total_laps: int

    def as_dict(self) -> dict:
        return {
            "itemId": self.item_id,
            "phase": self.phase,
            "seconds": self.seconds,
            "reps": self.reps,
            "lap": self.lap,
            "totalLaps": self.total_laps,
        }


def _item_steps(item: WorkoutExercise, lap: int, total_laps: int) -> list[TimerStep]:
    reps = item.reps[lap - 1] if item.reps else None
    seconds = None if item.reps else item.work_seconds
    steps = [TimerStep(item.pk, "work", seconds, reps, lap, total_laps)]
    if item.rest_seconds:
        steps.append(TimerStep(item.pk, "rest", item.rest_seconds, None, lap, total_laps))
    return steps


def build_timeline(workout: Workout) -> list[dict]:
    """Déroulé chronométré complet, en pas successifs prêts pour le minuteur."""
    items = list(workout.items.all())
    if not items:
        return []

    steps: list[TimerStep] = []
    if workout.format in INTERLEAVED_FORMATS:
        total_laps = items[0].rounds or 1
        for lap in range(1, total_laps + 1):
            for item in items:
                steps += _item_steps(item, lap, total_laps)
    else:
        for item in items:
            total_laps = item.rounds or 1
            for lap in range(1, total_laps + 1):
                steps += _item_steps(item, lap, total_laps)

    return [step.as_dict() for step in steps]
