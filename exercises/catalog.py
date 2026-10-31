"""Import du catalogue d'exercices livré avec l'application.

L'import se fait par lots : chaque appel traite une tranche et rend la main.
C'est ce découpage qui rend la progression mesurable à l'écran, sans thread ni
état partagé entre processus — la position d'avancement est portée par la
requête, et la seule source de vérité reste la base.

Toutes les opérations sont idempotentes : réimporter une tranche déjà chargée
met à jour les fiches au lieu de les dupliquer.
"""

import json
import shutil
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.db import transaction

from . import translation
from .models import Exercise, Muscle

#: Nombre d'exercices traités par appel. Assez petit pour qu'un lot reste bref
#: — la barre doit avancer visiblement — assez grand pour éviter des dizaines
#: d'allers-retours.
BATCH_SIZE = 75

#: Libellés français des groupes musculaires de la source, qui est en anglais.
MUSCLE_NAMES: dict[str, str] = {
    "abdominals": "Abdominaux",
    "abductors": "Abducteurs",
    "adductors": "Adducteurs",
    "biceps": "Biceps",
    "calves": "Mollets",
    "chest": "Pectoraux",
    "forearms": "Avant-bras",
    "glutes": "Fessiers",
    "hamstrings": "Ischio-jambiers",
    "lats": "Dorsaux",
    "lower back": "Bas du dos",
    "middle back": "Milieu du dos",
    "neck": "Cou",
    "quadriceps": "Quadriceps",
    "shoulders": "Épaules",
    "traps": "Trapèzes",
    "triceps": "Triceps",
}


#: Regroupement d'affichage des muscles par région du corps (issue #26).
#: Le tronc est séparé du haut du corps : le gainage est un travail à part
#: entière, pas un sous-produit du buste. Un slug absent d'ici (import futur
#: qui introduirait un nouveau groupe musculaire) rejoint « Autres » plutôt que
#: d'être perdu — voir `group_by_region`.
MUSCLE_REGIONS: dict[str, tuple[str, ...]] = {
    "Haut du corps": ("chest", "shoulders", "biceps", "triceps", "forearms", "neck"),
    "Dos": ("lats", "traps", "middle back", "lower back"),
    "Tronc": ("abdominals",),
    "Bas du corps": (
        "quadriceps",
        "hamstrings",
        "glutes",
        "calves",
        "abductors",
        "adductors",
    ),
}

#: Filtres rapides de l'historique des séances (issue #116) : un découpage plus
#: grossier et plus parlant que `MUSCLE_REGIONS` pour retrouver une séance d'un
#: coup de pouce. Clé = valeur du paramètre d'adresse, valeur = (libellé, slugs).
QUICK_ZONES: dict[str, tuple[str, tuple[str, ...]]] = {
    "bras": ("Bras", ("biceps", "triceps", "forearms")),
    "jambes": (
        "Jambes",
        ("quadriceps", "hamstrings", "glutes", "calves", "abductors", "adductors"),
    ),
    "dos": ("Dos", MUSCLE_REGIONS["Dos"]),
    "abdos": ("Abdos", ("abdominals",)),
}

#: Matériel corrigé par fiche (issue #117). La source classe la corde à sauter
#: sous « other », faute de valeur dédiée : c'est le seul exercice du catalogue
#: livré qui l'emploie (`Fast_Skipping` est une course sur place, sans corde).
EQUIPMENT_OVERRIDES: dict[str, str] = {"Rope_Jumping": "jump rope"}

#: Exercices écartés en mode plafond bas, sous 1,80 m (issue #131). Liste relue
#: fiche par fiche plutôt que déduite des noms : un motif comme « hop » ou
#: « overhead » attrape « Wood Chop » ou des extensions faites allongé, et en
#: manque d'autres (windmill, get-up). Mieux vaut un oubli à signaler qu'un
#: rapprochement hasardeux — même principe que `EQUIPMENT_OVERRIDES`.
LOW_CEILING_EXCLUDED: frozenset[str] = frozenset(
    {
        # Sauts : le corps entier quitte le sol, debout.
        "Alternate_Leg_Diagonal_Bound",
        "Bench_Jump",
        "Bench_Sprint",
        "Box_Jump_Multiple_Response",
        "Box_Skip",
        "Depth_Jump_Leap",
        "Double_Leg_Butt_Kick",
        "Dumbbell_Seated_Box_Jump",
        "Fast_Skipping",
        "Freehand_Jump_Squat",
        "Front_Box_Jump",
        "Front_Cone_Hops_or_hurdle_hops",
        "Hurdle_Hops",
        "Knee_Tuck_Jump",
        "Kneeling_Jump_Squat",
        "Lateral_Bound",
        "Lateral_Box_Jump",
        "Lateral_Cone_Hops",
        "Linear_Depth_Jump",
        "Quick_Leap",
        "Rocket_Jump",
        "Rope_Jumping",
        "Scissors_Jump",
        "Side_Hop-Sprint",
        "Side_Standing_Long_Jump",
        "Side_to_Side_Box_Shuffle",
        "Single-Leg_Hop_Progression",
        "Single-Leg_Lateral_Hop",
        "Single-Leg_Stride_Jump",
        "Single_Leg_Butt_Kick",
        "Single_Leg_Push-off",
        "Split_Jump",
        "Standing_Long_Jump",
        "Star_Jump",
        "Stride_Jump_Crossover",
        "Vertical_Swing",
        "Weighted_Jump_Squat",
        # Charge tenue ou lancée au-dessus de la tête, debout ou assis — les
        # variantes allongées ou à genoux restent permises.
        "Advanced_Kettlebell_Windmill",
        "Alternating_Cable_Shoulder_Press",
        "Alternating_Kettlebell_Press",
        "Arnold_Dumbbell_Press",
        "Barbell_Shoulder_Press",
        "Bradford_Rocky_Presses",
        "Cable_Rope_Overhead_Triceps_Extension",
        "Cable_Shoulder_Press",
        "Catch_and_Overhead_Throw",
        "Clean_and_Jerk",
        "Clean_and_Press",
        "Double_Kettlebell_Jerk",
        "Double_Kettlebell_Push_Press",
        "Double_Kettlebell_Snatch",
        "Double_Kettlebell_Windmill",
        "Dumbbell_One-Arm_Shoulder_Press",
        "Dumbbell_One-Arm_Triceps_Extension",
        "Dumbbell_Shoulder_Press",
        "Handstand_Push-Ups",
        "Hang_Snatch",
        "Hang_Snatch_-_Below_Knees",
        "Heaving_Snatch_Balance",
        "Jerk_Balance",
        "Kettlebell_Arnold_Press",
        "Kettlebell_Seated_Press",
        "Kettlebell_Seesaw_Press",
        "Kettlebell_Thruster",
        "Kettlebell_Turkish_Get-Up_Lunge_style",
        "Kettlebell_Turkish_Get-Up_Squat_style",
        "Kettlebell_Windmill",
        "Leverage_Shoulder_Press",
        "Low_Cable_Triceps_Extension",
        "Machine_Shoulder_Military_Press",
        "Muscle_Snatch",
        "One-Arm_Kettlebell_Clean_and_Jerk",
        "One-Arm_Kettlebell_Jerk",
        "One-Arm_Kettlebell_Military_Press_To_The_Side",
        "One-Arm_Kettlebell_Push_Press",
        "One-Arm_Kettlebell_Snatch",
        "One-Arm_Kettlebell_Split_Jerk",
        "One-Arm_Kettlebell_Split_Snatch",
        "One-Arm_Overhead_Kettlebell_Squats",
        "Overhead_Slam",
        "Overhead_Squat",
        "Power_Jerk",
        "Power_Snatch",
        "Power_Snatch_from_Blocks",
        "Push_Press",
        "Push_Press_-_Behind_the_Neck",
        "Seated_Barbell_Military_Press",
        "Seated_Cable_Shoulder_Press",
        "Seated_Triceps_Press",
        "See-Saw_Press_Alternating_Side_Press",
        "Shoulder_Press_-_With_Bands",
        "Sled_Overhead_Backward_Walk",
        "Sled_Overhead_Triceps_Extension",
        "Sledgehammer_Swings",
        "Smith_Machine_Overhead_Shoulder_Press",
        "Snatch",
        "Snatch_Balance",
        "Snatch_from_Blocks",
        "Speed_Band_Overhead_Triceps",
        "Split_Jerk",
        "Split_Snatch",
        "Squat_Jerk",
        "Standing_Barbell_Press_Behind_Neck",
        "Standing_Bradford_Press",
        "Standing_Dumbbell_Triceps_Extension",
        "Standing_Military_Press",
        "Standing_One-Arm_Dumbbell_Triceps_Extension",
        "Standing_Overhead_Barbell_Triceps_Extension",
        "Standing_Towel_Triceps_Extension",
        "Standing_Two-Arm_Overhead_Throw",
        "Triceps_Overhead_Extension_with_Rope",
        "Two-Arm_Kettlebell_Jerk",
        "Two-Arm_Kettlebell_Military_Press",
        # Suspendu à une barre de traction : elle se trouve au-dessus de la
        # tête, impossible à installer sous un plafond bas.
        "Band_Assisted_Pull-Up",
        "Chin-Up",
        "Gironda_Sternum_Chins",
        "Hanging_Leg_Raise",
        "Hanging_Pike",
        "Kipping_Muscle_Up",
        "Muscle_Up",
        "One_Arm_Chin-Up",
        "Pullups",
        "Rocky_Pull-Ups_Pulldowns",
        "Scapular_Pull-Up",
        "V-Bar_Pullup",
        "Wide-Grip_Rear_Pull-Up",
    }
)

#: Libellé du groupe accueillant un muscle inconnu des régions ci-dessus.
OTHER_REGION = "Autres"


def group_by_region(muscles) -> dict[str, list]:
    """Range des muscles par région, dans l'ordre de `MUSCLE_REGIONS`.

    Un groupe qui ne contient aucun des muscles fournis n'apparaît pas dans le
    résultat : un écran de sélection n'a pas à afficher une section vide.
    """
    slug_to_region = {slug: region for region, slugs in MUSCLE_REGIONS.items() for slug in slugs}

    grouped: dict[str, list] = {region: [] for region in MUSCLE_REGIONS}
    grouped[OTHER_REGION] = []

    for muscle in muscles:
        region = slug_to_region.get(muscle.slug, OTHER_REGION)
        grouped[region].append(muscle)

    return {region: items for region, items in grouped.items() if items}


def body_regions(muscles) -> list[str]:
    """Régions du corps sollicitées par un ensemble de muscles (issue #108).

    Réduit `group_by_region` à la seule liste des régions concernées, pour
    l'iconographie corporelle du déroulé de séance — qui n'a besoin que de
    savoir lesquelles éclairer, pas le détail des muscles qu'elles couvrent.
    `Autres` (muscle non mappé) n'a pas de zone dans l'icône : mieux vaut ne
    rien éclairer qu'un rapprochement hasardeux (même principe que le rappel
    d'exercice associé à une activité Apple Santé, issue #82).
    """
    return [region for region in group_by_region(muscles) if region != OTHER_REGION]


class CatalogError(Exception):
    """Source de catalogue absente ou illisible, avec un message actionnable."""


@dataclass(frozen=True)
class Progress:
    """Avancement de l'import, tel qu'affiché par la barre de progression."""

    imported: int
    total: int

    @property
    def done(self) -> bool:
        return self.imported >= self.total

    @property
    def percent(self) -> int:
        if not self.total:
            return 100
        return min(100, round(self.imported * 100 / self.total))


def source_path() -> Path:
    return Path(settings.EXERCISES_SOURCE)


def images_source_path() -> Path:
    return Path(settings.EXERCISES_IMAGES_SOURCE)


def sync_images(paths: list[str]) -> None:
    """Copie vers le stockage média les illustrations encore absentes (issue #29).

    Les fichiers sont vendorés dans le dépôt (licence Unlicense), au même
    chemin relatif que celui stocké sur l'exercice. Un fichier déjà copié n'est
    pas relu : l'opération reste bon marché à chaque réimport. Une source
    manquante est ignorée — les illustrations sont un supplément, jamais une
    condition pour que le référentiel se charge.
    """
    source_root = images_source_path()
    media_root = Path(settings.MEDIA_ROOT) / "exercises"

    for relative in paths:
        destination = media_root / relative
        if destination.exists():
            continue

        origin = source_root / relative
        if not origin.is_file():
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, destination)


@lru_cache(maxsize=1)
def _load(path: str, mtime: float) -> list[dict]:
    """Lit et met en cache le fichier source.

    Le catalogue pèse environ un mégaoctet et ne change pas entre deux lots :
    le relire à chaque appel coûterait plus que l'import lui-même. La date de
    modification fait partie de la clé pour qu'un fichier remplacé soit relu.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise CatalogError(
            f"Catalogue d'exercices introuvable : {path}. "
            "Vérifie le fichier livré avec l'application ou la variable EXERCISES_SOURCE."
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"Catalogue d'exercices illisible : {exc}") from exc

    if not isinstance(payload, list):
        raise CatalogError("Le catalogue doit être une liste d'exercices.")
    return payload


def entries() -> list[dict]:
    """Exercices de la source, dans l'ordre du fichier."""
    path = source_path()
    try:
        mtime = path.stat().st_mtime
    except OSError as exc:
        raise CatalogError(
            f"Catalogue d'exercices introuvable : {path}. "
            "Vérifie le fichier livré avec l'application ou la variable EXERCISES_SOURCE."
        ) from exc
    return _load(str(path), mtime)


def progress() -> Progress:
    """État d'avancement, mesuré sur la base et non sur un compteur en mémoire."""
    return Progress(imported=Exercise.objects.count(), total=len(entries()))


def is_loaded() -> bool:
    """Vrai lorsque le catalogue est en base au complet."""
    try:
        return progress().done
    except CatalogError:
        # Sans source lisible, rien ne pourra être chargé : mieux vaut laisser
        # l'application fonctionner que la bloquer sur un écran d'amorçage.
        return True


def ensure_muscles() -> dict[str, Muscle]:
    """Crée les groupes musculaires connus et retourne l'index par identifiant."""
    existing = {muscle.slug: muscle for muscle in Muscle.objects.all()}

    manquants = [
        Muscle(slug=slug, name=name) for slug, name in MUSCLE_NAMES.items() if slug not in existing
    ]
    if manquants:
        Muscle.objects.bulk_create(manquants, ignore_conflicts=True)
        existing = {muscle.slug: muscle for muscle in Muscle.objects.all()}

    return existing


def _valid(value: str | None, choices: type) -> str:
    """Ne retient une valeur de la source que si elle appartient aux choix connus."""
    return value if value in choices.values else ""


@transaction.atomic
def import_batch(offset: int, size: int | None = None, translate: bool = False) -> int:
    """Importe la tranche `[offset, offset + size)` et retourne la position atteinte.

    La transaction couvre le lot entier : une panne au milieu laisse la base
    telle qu'elle était, et l'écran de chargement rejoue simplement la tranche.

    `translate` ne s'active que depuis le rechargement à la demande (jamais au
    premier amorçage) : chaque fiche encore sans traduction reçoit un appel au
    fournisseur IA actif. Sans fournisseur configuré, ou en cas d'échec, la
    fiche garde ses consignes en anglais — voir `exercises.translation`.
    """
    source = entries()
    offset = max(0, min(offset, len(source)))
    tranche = source[offset : offset + (size or BATCH_SIZE)]

    if not tranche:
        return offset

    muscles = ensure_muscles()

    for entry in tranche:
        slug = entry.get("id") or entry.get("name")
        if not slug:
            continue

        exercise, _ = Exercise.objects.update_or_create(
            slug=slug,
            defaults={
                "name": entry.get("name") or slug,
                "category": _valid(entry.get("category"), Exercise.Category),
                "level": _valid(entry.get("level"), Exercise.Level),
                "force": _valid(entry.get("force"), Exercise.Force),
                "mechanic": _valid(entry.get("mechanic"), Exercise.Mechanic),
                "equipment": _valid(
                    EQUIPMENT_OVERRIDES.get(slug, entry.get("equipment")), Exercise.Equipment
                ),
                "instructions": entry.get("instructions") or [],
                "images": entry.get("images") or [],
            },
        )
        exercise.primary_muscles.set(_resolve(entry.get("primaryMuscles"), muscles))
        exercise.secondary_muscles.set(_resolve(entry.get("secondaryMuscles"), muscles))

        sync_images(exercise.images)

        if translate and exercise.instructions and not exercise.instructions_fr:
            translated = translation.translate_instructions(exercise.instructions)
            if translated:
                exercise.instructions_fr = translated
                exercise.save(update_fields=["instructions_fr"])

    return offset + len(tranche)


def _resolve(slugs: list[str] | None, muscles: dict[str, Muscle]) -> list[Muscle]:
    """Traduit les identifiants de muscles, en créant ceux qu'on ne connaissait pas."""
    resolved = []
    for slug in slugs or []:
        muscle = muscles.get(slug)
        if muscle is None:
            # Une version ultérieure de la source peut introduire un groupe
            # musculaire absent de la table de traduction : il est conservé
            # sous son identifiant plutôt que perdu.
            muscle, _ = Muscle.objects.get_or_create(slug=slug, defaults={"name": slug})
            muscles[slug] = muscle
        resolved.append(muscle)
    return resolved


def import_all(translate: bool = False) -> int:
    """Importe le catalogue entier et retourne le nombre d'exercices traités."""
    total = len(entries())
    offset = 0
    while offset < total:
        offset = import_batch(offset, translate=translate)
    return total
