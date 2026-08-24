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


def _item_steps(
    item: WorkoutExercise, lap: int, total_laps: int, *, include_rest: bool = True
) -> list[TimerStep]:
    """Un pas d'effort, suivi de son repos — sauf `include_rest=False` : quand une
    récupération suit immédiatement (issue #60) ou que la séance s'arrête juste après
    (issue #66), un repos individuel ne servirait à rien."""
    reps = item.reps[lap - 1] if item.reps else None
    seconds = None if item.reps else item.work_seconds
    steps = [TimerStep(item.pk, "work", seconds, reps, lap, total_laps)]
    if item.rest_seconds and include_rest:
        steps.append(TimerStep(item.pk, "rest", item.rest_seconds, None, lap, total_laps))
    return steps


def build_timeline(workout: Workout) -> list[dict]:
    """Déroulé chronométré complet, en pas successifs prêts pour le minuteur.

    Un pas de récupération (issue #44) sépare deux tours de circuit/HIIT, ou
    deux blocs de Tabata/Pyramide — jamais après le dernier, la séance
    s'arrête plutôt que de marquer une pause qui ne sert plus à rien. Distinct
    du repos entre exercices porté par chaque `WorkoutExercise` : lu ici
    directement sur `workout.recovery_seconds`, pas caché, comme lui, à chaque
    rendu de l'écran de détail. Le repos individuel qui suivrait le dernier
    exercice d'un tour/round est omis quand une récupération lui succède
    immédiatement (issue #60), et plus largement quand rien ne le suit du tout
    — le dernier exercice du dernier tour/circuit ne marque pas non plus son
    propre repos (issue #66) : la séance s'arrête juste après, un repos n'y
    servirait à rien de plus qu'après le dernier pas de récupération.
    """
    items = list(workout.items.all())
    if not items:
        return []

    recovery = workout.recovery_seconds or 0
    steps: list[TimerStep] = []
    if workout.format in INTERLEAVED_FORMATS:
        total_laps = items[0].rounds or 1
        for lap in range(1, total_laps + 1):
            recovery_follows = bool(recovery and lap < total_laps)
            is_final_lap = lap == total_laps
            for position, item in enumerate(items):
                is_last_of_lap = position == len(items) - 1
                omit_rest = is_last_of_lap and (recovery_follows or is_final_lap)
                steps += _item_steps(item, lap, total_laps, include_rest=not omit_rest)
            if recovery_follows:
                steps.append(TimerStep(items[-1].pk, "recovery", recovery, None, lap, total_laps))
    else:
        for index, item in enumerate(items):
            total_laps = item.rounds or 1
            recovery_follows = bool(recovery and index < len(items) - 1)
            is_final_item = index == len(items) - 1
            for lap in range(1, total_laps + 1):
                is_last_lap = lap == total_laps
                omit_rest = is_last_lap and (recovery_follows or is_final_item)
                steps += _item_steps(item, lap, total_laps, include_rest=not omit_rest)
            if recovery_follows:
                steps.append(TimerStep(item.pk, "recovery", recovery, None, total_laps, total_laps))

    return [step.as_dict() for step in steps]
