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

#: Plancher d'une pyramide : en dessous, l'exercice devient un échauffement,
#: pas un temps de travail. Le pic est réglable (issue #34) ; le plancher, non.
PYRAMID_FLOOR_REPS = 6
MIN_PYRAMID_PEAK = PYRAMID_FLOOR_REPS
MAX_PYRAMID_PEAK = 20


@dataclass(frozen=True)
class Periods:
    """Réglages par défaut d'un format : effort, repos entre séries, récupération
    entre blocs, pic de répétitions. `work` vaut `None` pour la pyramide, qui se
    compte en répétitions et non en secondes ; `peak_reps` ne vaut quelque chose
    que pour elle (issue #34).
    """

    work: int | None
    rest: int
    recovery: int
    peak_reps: int | None = None


#: Recette de chaque format. Rassemblées ici plutôt que dispersées dans les
#: fonctions de minutage, pour que le formulaire de séance puisse proposer un
#: réglage par format sans dupliquer ces valeurs (issue #26).
FORMAT_PERIODS: dict[str, Periods] = {
    Workout.Format.TABATA: Periods(work=20, rest=10, recovery=60),
    Workout.Format.HIIT: Periods(work=40, rest=20, recovery=60),
    Workout.Format.CIRCUIT: Periods(work=45, rest=15, recovery=90),
    Workout.Format.PYRAMID: Periods(work=None, rest=75, recovery=0, peak_reps=12),
}

#: Largeur (nombre d'exercices distincts par tour) explorée par `_circuit`,
#: selon le format. Avec les mêmes temps de travail/repos, HIIT et Circuit
#: convergeaient sur la même forme — `_circuit` ne cherchait que le
#: remplissage le plus complet, indifférent au format qui l'appelle. Un HIIT
#: vise la variété (beaucoup d'exercices, peu de tours) ; un circuit vise la
#: répétition (peu d'exercices, plusieurs tours) — deux plages disjointes le
#: garantissent, quelle que soit la durée demandée.
HIIT_WIDTHS = range(8, 15)
CIRCUIT_WIDTHS = range(3, 7)

#: Bornes appliquées aux temps personnalisés, côté formulaire comme côté
#: générateur : un effort de moins de 5 s ou un repos de plus de 3 min ne
#: correspond à aucun entraînement réel.
MIN_WORK_SECONDS = 5
MAX_WORK_SECONDS = 180
MIN_REST_SECONDS = 0
MAX_REST_SECONDS = 180

#: Le repos entre deux tours/blocs (issue #44) sépare une reprise, pas un
#: exercice : la borne haute est plus généreuse qu'un simple repos.
MIN_RECOVERY_SECONDS = 0
MAX_RECOVERY_SECONDS = 300

#: Crans proposés pour éditer le repos entre les tours depuis l'écran de
#: détail (issue #44 suite) : une règle graduée (`.ugg-ruler`), pas un champ
#: libre — peu de valeurs utiles, comme la durée de la séance. Couvre déjà les
#: défauts de Tabata/HIIT (60) et Circuit (90) ; celui de la Pyramide (0) est
#: hors plage, RECOVERY_RULER_DEFAULT sert alors de repli à l'affichage.
RECOVERY_RULER_SECONDS = (30, 60, 90, 120, 150, 180)
RECOVERY_RULER_DEFAULT = 60


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


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
    #: Résolu par `build_blueprint` après coup (issue #44) — le repos entre
    #: tours/blocs, distinct du repos entre exercices porté par chaque `Slot`.
    recovery_seconds: int = 0

    @property
    def needed(self) -> int:
        return max((slot.exercise_rank for slot in self.slots), default=-1) + 1


# --------------------------------------------------------------------------- #
# Minutage : une recette par format
# --------------------------------------------------------------------------- #


def _tabata(seconds: int, work: int, rest: int, recovery: int) -> Blueprint:
    """Blocs d'un exercice : 8 séries d'effort/repos, une pause entre chaque bloc."""
    rounds = 8
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


def _circuit(
    seconds: int, work: int, rest: int, recovery: int, label: str, widths: range
) -> Blueprint:
    """Un tour de plusieurs exercices, répété. La largeur du tour suit la durée,
    dans la plage proposée par l'appelant (`HIIT_WIDTHS` / `CIRCUIT_WIDTHS`)."""
    best = None

    # On essaie chaque largeur possible et on garde celle qui remplit le mieux
    # la durée demandée.
    for width in widths:
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


def _pyramid_ladder(peak: int) -> list[int]:
    """Paliers de répétitions, du pic demandé jusqu'au plancher, par pas de deux.

    Toujours terminé par `PYRAMID_FLOOR_REPS`, quelle que soit la parité du pic
    — un pic impair ne doit pas sauter le plancher (issue #34).
    """
    ladder = []
    current = peak
    while current > PYRAMID_FLOOR_REPS:
        ladder.append(current)
        current -= 2
    ladder.append(PYRAMID_FLOOR_REPS)
    return ladder


def _pyramid_shape(peak: int) -> list[int]:
    """Pyramide symétrique : descend du pic au plancher, puis remonte."""
    descending = _pyramid_ladder(peak)
    return descending + descending[-2::-1]


def _pyramid_shapes(peak: int) -> list[list[int]]:
    """Échelle de pyramides, du pic demandé au plus court. Le générateur retient
    celle qui occupe le mieux la durée demandée : une pyramide est un bloc
    indivisible, et s'entêter sur le pic demandé laisserait parfois un tiers de
    la séance vide.
    """
    return [_pyramid_shape(p) for p in _pyramid_ladder(peak)]


def _pyramid(seconds: int, rest: int, peak: int) -> Blueprint:
    """Répétitions décroissantes puis croissantes, une pyramide par exercice."""
    candidates = []
    for shape in _pyramid_shapes(peak):
        cost = sum(rep * SECONDS_PER_REP + rest for rep in shape)
        count = seconds // cost
        if count >= 1:
            candidates.append((count * cost, shape, count, cost))

    if not candidates:
        # Durée plus courte que la plus petite pyramide : on en donne une seule,
        # la plus resserrée, quitte à mordre légèrement sur le temps annoncé.
        shape = _pyramid_shape(PYRAMID_FLOOR_REPS)
        cost = sum(rep * SECONDS_PER_REP + rest for rep in shape)
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
            rest_seconds=rest,
            reps=reps,
        )
        for index in range(count)
    ]
    return Blueprint(slots, count * per_exercise)


def build_blueprint(
    workout_format: str,
    duration_minutes: int,
    work_seconds: int | None = None,
    rest_seconds: int | None = None,
    peak_reps: int | None = None,
    recovery_seconds: int | None = None,
) -> Blueprint:
    """Déroulé et minutage du format demandé, sans exercice encore attribué.

    `work_seconds` / `rest_seconds` / `peak_reps` / `recovery_seconds`
    remplacent, quand fournis, les valeurs par défaut du format — bornés dans
    tous les cas : un formulaire mal rempli ne doit pas produire une séance
    absurde plutôt qu'un message d'erreur. `peak_reps` ne s'applique qu'à la
    pyramide (issue #34). `recovery_seconds` sépare deux tours ou deux blocs,
    pas deux exercices (issue #44) — toujours résolu sur le blueprint renvoyé,
    même pour la pyramide qui ne s'en sert pas pour son propre minutage.
    """
    periods = FORMAT_PERIODS.get(workout_format)
    if periods is None:
        raise GenerationError(f"Type de travail inconnu : {workout_format}.")

    seconds = duration_minutes * 60
    rest = rest_seconds if rest_seconds is not None else periods.rest
    rest = _clamp(rest, MIN_REST_SECONDS, MAX_REST_SECONDS)

    recovery = recovery_seconds if recovery_seconds is not None else periods.recovery
    recovery = _clamp(recovery, MIN_RECOVERY_SECONDS, MAX_RECOVERY_SECONDS)

    work = periods.work
    if work is not None:
        work = work_seconds if work_seconds is not None else work
        work = _clamp(work, MIN_WORK_SECONDS, MAX_WORK_SECONDS)

    peak = periods.peak_reps
    if peak is not None:
        peak = peak_reps if peak_reps is not None else peak
        peak = _clamp(peak, MIN_PYRAMID_PEAK, MAX_PYRAMID_PEAK)

    if workout_format == Workout.Format.TABATA:
        blueprint = _tabata(seconds, work, rest, recovery)
    elif workout_format == Workout.Format.HIIT:
        blueprint = _circuit(seconds, work, rest, recovery, label="HIIT", widths=HIIT_WIDTHS)
    elif workout_format == Workout.Format.CIRCUIT:
        blueprint = _circuit(seconds, work, rest, recovery, label="Circuit", widths=CIRCUIT_WIDTHS)
    else:
        blueprint = _pyramid(seconds, rest, peak)

    blueprint.recovery_seconds = recovery
    return blueprint


# --------------------------------------------------------------------------- #
# Sélection des exercices
# --------------------------------------------------------------------------- #


def eligible_exercises(
    user, muscles: list[str], equipment: list[str] | None = None
) -> QuerySet[Exercise]:
    """Exercices réalisables par cet utilisateur, ciblant les muscles demandés.

    `equipment` restreint le matériel réellement pris en compte pour cette
    séance (issue #32) : un sous-ensemble du matériel configuré, coché
    directement dans le formulaire, indépendant de la configuration
    elle-même. `None` retient tout le matériel configuré, comme avant cette
    option ; une liste, même vide, est prise au mot.
    """
    owned = set(UserEquipment.objects.filter(user=user).values_list("equipment", flat=True))
    if equipment is not None:
        owned &= set(equipment)
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


def select_exercises(
    user,
    muscles: list[str],
    needed: int,
    ratio: int,
    rng,
    equipment: list[str] | None = None,
) -> list[Exercise]:
    """Tire les exercices de la séance, en y glissant la part de favoris demandée.

    Les favoris ne sont pas privilégiés dans l'absolu : ils occupent la part
    réclamée, ni plus ni moins. C'est ce qui évite une séance entièrement
    composée de mouvements inconnus.
    """
    pool = list(eligible_exercises(user, muscles, equipment))
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


def load_options(user, equipment: list[str] | None = None) -> dict[str, list[Decimal]]:
    """Charges disponibles, par matériel pris en compte (voir `eligible_exercises`)."""
    queryset = UserEquipment.objects.filter(user=user)
    if equipment is not None:
        queryset = queryset.filter(equipment__in=equipment)
    return {item.equipment: item.available_loads() for item in queryset}


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
    work_seconds: int | None = None,
    rest_seconds: int | None = None,
    peak_reps: int | None = None,
    recovery_seconds: int | None = None,
    equipment: list[str] | None = None,
    name: str = "",
    rng: random.Random | None = None,
) -> Workout:
    """Compose et enregistre une séance.

    `equipment` restreint le matériel configuré retenu pour cette séance
    (issue #32) — `None` le prend en entier, comme avant cette option.
    `peak_reps` ne s'applique qu'à la pyramide (issue #34). `name` se règle
    dès la composition (issue #44), en plus du renommage depuis l'écran de
    détail. `recovery_seconds` sépare deux tours ou deux blocs, pas deux
    exercices (issue #44 suite) — la valeur résolue est celle enregistrée,
    jamais `None`, contrairement à `work_seconds`/`rest_seconds`/`peak_reps`.
    """
    # Tirage de variété, pas de secret : le générateur standard convient, et un
    # `Random` injectable rend la composition reproductible en test.
    rng = rng or random.Random()  # noqa: S311

    blueprint = build_blueprint(
        workout_format, duration_minutes, work_seconds, rest_seconds, peak_reps, recovery_seconds
    )
    exercises = select_exercises(user, muscles, blueprint.needed, favorites_ratio, rng, equipment)
    options = load_options(user, equipment)

    workout = Workout.objects.create(
        user=user,
        name=name,
        duration_minutes=duration_minutes,
        format=workout_format,
        favorites_ratio=favorites_ratio,
        work_seconds=work_seconds,
        rest_seconds=rest_seconds,
        peak_reps=peak_reps,
        recovery_seconds=blueprint.recovery_seconds,
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


# --------------------------------------------------------------------------- #
# Rafraîchissement d'un exercice (issue #44)
# --------------------------------------------------------------------------- #


def refresh_exercise(item: WorkoutExercise, rng: random.Random | None = None) -> Exercise:
    """Remplace l'exercice d'une ligne de séance par un autre compatible.

    Le créneau (rounds, temps, répétitions, bloc) ne change pas — seul
    l'exercice et sa charge. Le matériel retenu est celui *actuellement*
    configuré, pas le sous-ensemble figé à la génération (non conservé) : le
    but est de refléter la réalité du moment, pas les réglages d'alors. Le
    déroulé peut déjà contenir des doublons entre lignes (repli de
    `select_exercises` sur un catalogue trop pauvre) ; cette fonction les
    traite comme n'importe quel autre exercice déjà utilisé.
    """
    rng = rng or random.Random()  # noqa: S311
    workout = item.workout
    muscles = list(workout.muscles.values_list("slug", flat=True))

    pool = list(eligible_exercises(workout.user, muscles).exclude(pk=item.exercise_id))
    if not pool:
        raise GenerationError(
            "Aucun autre exercice ne correspond à ton matériel et à ces parties du "
            "corps pour l'instant."
        )

    used = set(workout.items.exclude(pk=item.pk).values_list("exercise_id", flat=True))
    # Repli : autoriser un doublon plutôt qu'échouer si rien d'autre n'est disponible.
    candidates = [exercise for exercise in pool if exercise.pk not in used] or pool
    exercise = rng.choice(candidates)

    options = load_options(workout.user)
    base = _pick_load(exercise, options)
    available = options.get(exercise.equipment) or []
    loads = (
        _pyramid_loads(base, item.reps, available)
        if item.reps
        else ([float(base)] if base is not None else [])
    )

    item.exercise = exercise
    item.loads = loads
    item.save(update_fields=["exercise", "loads"])
    return exercise
