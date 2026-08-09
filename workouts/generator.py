"""Composition d'une séance à partir du catalogue et du matériel de l'utilisateur.

Module sans accès HTTP ni requête au fournisseur d'IA : la structure et le
minutage sont de l'arithmétique, et doivent l'être. Un format comme le Tabata
n'admet aucune approximation — 8 rounds de 20 s et 10 s font 4 minutes, pas
« environ 4 minutes ».

La séance ne dépasse jamais la durée demandée : elle se remplit par blocs
entiers, et le reliquat est assumé plutôt que comblé par un bloc tronqué.
"""

import random
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, QuerySet

from accounts.models import UserEquipment
from exercises.models import Exercise, Favorite, Muscle

from .models import Workout, WorkoutExercise

#: Toujours disponible : personne n'a besoin de matériel pour un gainage.
BODYWEIGHT = "body only"

#: Catégories écartées d'une séance : un étirement ou un passage au rouleau ne
#: constitue pas un temps de travail.
EXCLUDED_CATEGORIES = ("stretching",)

#: Secondes par répétition, pour estimer la durée d'une série chiffrée.
SECONDS_PER_REP = 3

#: Repos entre deux séries d'une pyramide.
PYRAMID_REST = 75

#: Formes de pyramide, de la plus longue à la plus courte. Le générateur retient
#: celle qui occupe le mieux la durée demandée : une pyramide est un bloc
#: indivisible, et s'entêter sur la forme canonique laisserait parfois un tiers
#: de la séance vide.
PYRAMID_SHAPES = (
    (12, 10, 8, 6, 8, 10, 12),
    (10, 8, 6, 8, 10),
    (8, 6, 8),
)

#: Remplissage jugé suffisant. On garde la pyramide la plus complète qui
#: l'atteint, plutôt que celle qui remplit le mieux : viser le seul remplissage
#: retiendrait presque toujours la forme la plus courte, qui se divise mieux, et
#: la pyramide n'aurait plus grand-chose d'une pyramide.
MIN_FILL_RATIO = 0.8

#: Part de la plage de charges retenue selon l'exigence de l'exercice.
LOAD_RATIO = {
    Exercise.Level.BEGINNER: 0.35,
    Exercise.Level.INTERMEDIATE: 0.55,
    Exercise.Level.EXPERT: 0.75,
}


class GenerationError(Exception):
    """Séance impossible à composer, avec un message qui dit quoi changer."""


@dataclass
class Slot:
    """Emplacement du déroulé, avant qu'un exercice ne lui soit attribué."""

    block_index: int
    block_label: str
    #: Rang de l'exercice distinct à utiliser — deux slots de même rang portent
    #: le même exercice, ce qui fait revenir un circuit à chaque tour.
    exercise_rank: int
    rounds: int
    work_seconds: int | None = None
    rest_seconds: int | None = None
    reps: list[int] = field(default_factory=list)


@dataclass
class Blueprint:
    """Déroulé complet d'une séance, encore vierge d'exercices."""

    slots: list[Slot]
    total_seconds: int

    @property
    def needed(self) -> int:
        return max((slot.exercise_rank for slot in self.slots), default=-1) + 1


# --------------------------------------------------------------------------- #
# Minutage : une recette par format
# --------------------------------------------------------------------------- #


def _tabata(seconds: int) -> Blueprint:
    """Blocs d'un exercice : 8 fois (20 s d'effort, 10 s de repos), 1 min entre blocs."""
    work, rest, rounds, recovery = 20, 10, 8, 60
    block = rounds * (work + rest)

    count = max(1, (seconds + recovery) // (block + recovery))
    slots = [
        Slot(
            block_index=index,
            block_label=f"Bloc {index + 1}",
            exercise_rank=index,
            rounds=rounds,
            work_seconds=work,
            rest_seconds=rest,
        )
        for index in range(count)
    ]
    return Blueprint(slots, count * block + (count - 1) * recovery)


def _circuit(seconds: int, work: int, rest: int, recovery: int, label: str) -> Blueprint:
    """Un tour de plusieurs exercices, répété. La largeur du tour suit la durée."""
    best = None

    # On essaie chaque largeur de circuit et on garde celle qui remplit le mieux
    # la durée demandée : à durée égale, un tour large répété peu de fois n'a pas
    # le même intérêt qu'un tour court répété souvent.
    for width in range(3, 11):
        lap = width * (work + rest)
        rounds = (seconds + recovery) // (lap + recovery)
        if rounds < 1:
            continue
        total = rounds * lap + (rounds - 1) * recovery
        if best is None or total > best[0]:
            best = (total, width, rounds)

    if best is None:
        # Durée trop courte pour le moindre tour : on en fait un, resserré.
        width = max(1, seconds // (work + rest))
        return Blueprint(
            [Slot(0, f"{label} — 1 tour", rank, 1, work, rest) for rank in range(max(1, width))],
            max(1, width) * (work + rest),
        )

    total, width, rounds = best
    slots = [
        Slot(
            block_index=0,
            block_label=f"{label} — {rounds} tour{'s' if rounds > 1 else ''}",
            exercise_rank=rank,
            rounds=rounds,
            work_seconds=work,
            rest_seconds=rest,
        )
        for rank in range(width)
    ]
    return Blueprint(slots, total)


def _pyramid(seconds: int) -> Blueprint:
    """Répétitions décroissantes puis croissantes, une pyramide par exercice."""
    candidates = []
    for shape in PYRAMID_SHAPES:
        cost = sum(rep * SECONDS_PER_REP + PYRAMID_REST for rep in shape)
        count = seconds // cost
        if count >= 1:
            candidates.append((count * cost, list(shape), count, cost))

    if not candidates:
        # Durée plus courte que la plus petite pyramide : on en donne une seule,
        # la plus resserrée, quitte à mordre légèrement sur le temps annoncé.
        shape = list(PYRAMID_SHAPES[-1])
        cost = sum(rep * SECONDS_PER_REP + PYRAMID_REST for rep in shape)
        candidates = [(cost, shape, 1, cost)]

    # Les formes sont parcourues de la plus complète à la plus courte : la
    # première qui remplit assez l'emporte.
    chosen = next(
        (item for item in candidates if item[0] >= seconds * MIN_FILL_RATIO),
        max(candidates, key=lambda item: item[0]),
    )
    _, reps, count, per_exercise = chosen
    slots = [
        Slot(
            block_index=index,
            block_label=f"Pyramide {index + 1}",
            exercise_rank=index,
            rounds=len(reps),
            rest_seconds=PYRAMID_REST,
            reps=reps,
        )
        for index in range(count)
    ]
    return Blueprint(slots, count * per_exercise)


def build_blueprint(workout_format: str, duration_minutes: int) -> Blueprint:
    """Déroulé et minutage du format demandé, sans exercice encore attribué."""
    seconds = duration_minutes * 60

    if workout_format == Workout.Format.TABATA:
        return _tabata(seconds)
    if workout_format == Workout.Format.HIIT:
        return _circuit(seconds, work=40, rest=20, recovery=60, label="HIIT")
    if workout_format == Workout.Format.CIRCUIT:
        return _circuit(seconds, work=45, rest=15, recovery=90, label="Circuit")
    if workout_format == Workout.Format.PYRAMID:
        return _pyramid(seconds)

    raise GenerationError(f"Type de travail inconnu : {workout_format}.")


# --------------------------------------------------------------------------- #
# Sélection des exercices
# --------------------------------------------------------------------------- #


def eligible_exercises(user, muscles: list[str]) -> QuerySet[Exercise]:
    """Exercices réalisables par cet utilisateur, ciblant les muscles demandés."""
    owned = set(UserEquipment.objects.filter(user=user).values_list("equipment", flat=True))
    # Le poids du corps ne se déclare pas : il est toujours disponible.
    owned.add(BODYWEIGHT)
    owned.add("")

    queryset = Exercise.objects.filter(equipment__in=owned).exclude(
        category__in=EXCLUDED_CATEGORIES
    )

    if muscles:
        queryset = queryset.filter(
            Q(primary_muscles__slug__in=muscles) | Q(secondary_muscles__slug__in=muscles)
        ).distinct()

    return queryset


def select_exercises(user, muscles: list[str], needed: int, ratio: int, rng) -> list[Exercise]:
    """Tire les exercices de la séance, en y glissant la part de favoris demandée.

    Les favoris ne sont pas privilégiés dans l'absolu : ils occupent la part
    réclamée, ni plus ni moins. C'est ce qui évite une séance entièrement
    composée de mouvements inconnus.
    """
    pool = list(eligible_exercises(user, muscles))
    if not pool:
        raise GenerationError(
            "Aucun exercice ne correspond à ce matériel et à ces parties du corps. "
            "Élargis la sélection, ou complète ton matériel depuis ton profil."
        )

    marked = set(
        Favorite.objects.filter(user=user, exercise__in=pool).values_list("exercise_id", flat=True)
    )
    favorites = [item for item in pool if item.pk in marked]
    others = [item for item in pool if item.pk not in marked]

    rng.shuffle(favorites)
    rng.shuffle(others)

    wanted_favorites = min(round(needed * ratio / 100), len(favorites))
    chosen = favorites[:wanted_favorites]
    chosen += others[: needed - len(chosen)]

    # Les favoris comblent ce que le reste du catalogue ne fournit pas, et
    # réciproquement : mieux vaut un favori de plus que prévu qu'un trou.
    if len(chosen) < needed:
        chosen += [item for item in favorites[wanted_favorites:] if item not in chosen]

    rng.shuffle(chosen)

    # Catalogue plus pauvre que la séance n'est longue : on repasse sur les mêmes
    # exercices plutôt que d'écourter la séance.
    distinct = list(chosen)
    while len(chosen) < needed:
        chosen.append(distinct[len(chosen) % len(distinct)])

    return chosen[:needed]


# --------------------------------------------------------------------------- #
# Charges
# --------------------------------------------------------------------------- #


def load_options(user) -> dict[str, list[Decimal]]:
    """Charges disponibles, par matériel."""
    return {
        item.equipment: item.available_loads() for item in UserEquipment.objects.filter(user=user)
    }


def _pick_load(exercise: Exercise, options: dict[str, list[Decimal]]) -> Decimal | None:
    """Charge de départ : un cran réellement disponible, calé sur l'exigence du mouvement."""
    loads = options.get(exercise.equipment) or []
    if not loads:
        return None

    ratio = LOAD_RATIO.get(exercise.level, 0.5)
    index = min(len(loads) - 1, round((len(loads) - 1) * ratio))
    return loads[index]


def _pyramid_loads(base: Decimal | None, reps: list[int], available: list[Decimal]) -> list[float]:
    """Charge par série : elle monte quand les répétitions descendent."""
    if base is None or not available:
        return []

    start = available.index(base) if base in available else 0
    heaviest = max(reps)
    loads = []
    for rep in reps:
        # Deux crans au-dessus pour la série la plus courte, la base pour la plus longue.
        offset = round((heaviest - rep) / max(1, heaviest - min(reps)) * 2)
        loads.append(float(available[min(len(available) - 1, start + offset)]))
    return loads


# --------------------------------------------------------------------------- #
# Assemblage
# --------------------------------------------------------------------------- #


@transaction.atomic
def generate(
    *,
    user,
    duration_minutes: int,
    workout_format: str,
    muscles: list[str],
    favorites_ratio: int = 25,
    rng: random.Random | None = None,
) -> Workout:
    """Compose et enregistre une séance."""
    # Tirage de variété, pas de secret : le générateur standard convient, et un
    # `Random` injectable rend la composition reproductible en test.
    rng = rng or random.Random()  # noqa: S311

    blueprint = build_blueprint(workout_format, duration_minutes)
    exercises = select_exercises(user, muscles, blueprint.needed, favorites_ratio, rng)
    options = load_options(user)

    workout = Workout.objects.create(
        user=user,
        duration_minutes=duration_minutes,
        format=workout_format,
        favorites_ratio=favorites_ratio,
        planned_seconds=blueprint.total_seconds,
    )
    if muscles:
        workout.muscles.set(list(Muscle.objects.filter(slug__in=muscles)))

    items = []
    for position, slot in enumerate(blueprint.slots, start=1):
        exercise = exercises[slot.exercise_rank]
        base = _pick_load(exercise, options)
        available = options.get(exercise.equipment) or []

        if slot.reps:
            loads = _pyramid_loads(base, slot.reps, available)
        else:
            loads = [float(base)] if base is not None else []

        items.append(
            WorkoutExercise(
                workout=workout,
                position=position,
                block_index=slot.block_index,
                block_label=slot.block_label,
                exercise=exercise,
                rounds=slot.rounds,
                work_seconds=slot.work_seconds,
                rest_seconds=slot.rest_seconds,
                reps=slot.reps,
                loads=loads,
            )
        )

    WorkoutExercise.objects.bulk_create(items)
    return workout
