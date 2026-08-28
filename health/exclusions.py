"""Exclusion des entrées supprimées ou modifiées manuellement (issue #81).

Une entrée supprimée — ou dont le type a été changé — ne doit plus jamais
être recréée par un réimport (#70) ou par l'API d'ingestion (#71) : comme les
modèles n'ont pas d'identifiant HealthKit stable, l'exclusion s'appuie sur la
même clé naturelle que l'upsert (`health.ingest`), consultée avant chaque
écriture.
"""

from datetime import UTC, datetime

from .models import ExcludedImport


def _instant(value: datetime) -> str:
    """Représentation canonique d'un instant, indépendante du fuseau d'origine.

    Un export Apple Health porte l'heure locale au moment de la mesure
    (`+01:00`…) ; une fois en base, Django la relit normalisée en UTC. Sans
    cette conversion explicite, la même seconde produirait deux clés
    différentes selon qu'elle vient d'être analysée ou relue depuis la base
    — et l'exclusion ne matcherait jamais.
    """
    return value.astimezone(UTC).isoformat()


def weight_key(recorded_at: datetime) -> str:
    return _instant(recorded_at)


def activity_key(activity_type: str, started_at: datetime) -> str:
    return f"{activity_type}|{_instant(started_at)}"


def exclude_weight(user, recorded_at: datetime) -> None:
    ExcludedImport.objects.get_or_create(
        user=user, kind=ExcludedImport.Kind.WEIGHT, natural_key=weight_key(recorded_at)
    )


def exclude_activity(user, activity_type: str, started_at: datetime) -> None:
    ExcludedImport.objects.get_or_create(
        user=user,
        kind=ExcludedImport.Kind.ACTIVITY,
        natural_key=activity_key(activity_type, started_at),
    )


def is_weight_excluded(user, recorded_at: datetime) -> bool:
    return ExcludedImport.objects.filter(
        user=user, kind=ExcludedImport.Kind.WEIGHT, natural_key=weight_key(recorded_at)
    ).exists()


def is_activity_excluded(user, activity_type: str, started_at: datetime) -> bool:
    return ExcludedImport.objects.filter(
        user=user,
        kind=ExcludedImport.Kind.ACTIVITY,
        natural_key=activity_key(activity_type, started_at),
    ).exists()
