"""Import du catalogue d'exercices livré avec l'application.

L'import se fait par lots : chaque appel traite une tranche et rend la main.
C'est ce découpage qui rend la progression mesurable à l'écran, sans thread ni
état partagé entre processus — la position d'avancement est portée par la
requête, et la seule source de vérité reste la base.

Toutes les opérations sont idempotentes : réimporter une tranche déjà chargée
met à jour les fiches au lieu de les dupliquer.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.db import transaction

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
def import_batch(offset: int, size: int | None = None) -> int:
    """Importe la tranche `[offset, offset + size)` et retourne la position atteinte.

    La transaction couvre le lot entier : une panne au milieu laisse la base
    telle qu'elle était, et l'écran de chargement rejoue simplement la tranche.
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
                "equipment": _valid(entry.get("equipment"), Exercise.Equipment),
                "instructions": entry.get("instructions") or [],
                "images": entry.get("images") or [],
            },
        )
        exercise.primary_muscles.set(_resolve(entry.get("primaryMuscles"), muscles))
        exercise.secondary_muscles.set(_resolve(entry.get("secondaryMuscles"), muscles))

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


def import_all() -> int:
    """Importe le catalogue entier et retourne le nombre d'exercices traités."""
    total = len(entries())
    offset = 0
    while offset < total:
        offset = import_batch(offset)
    return total
