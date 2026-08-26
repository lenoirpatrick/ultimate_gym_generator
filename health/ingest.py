"""Écriture idempotente des mesures et activités, partagée par deux entrées.

L'import d'un export Apple Health (#70, `health.importer`) et l'API POST à
distance (#71, `health.views.ingest`) reçoivent la même forme de données —
seule la source diffère (fichier vs JSON). Centraliser l'upsert ici évite que
les deux évoluent séparément et se mettent à diverger sur la clé d'unicité.
"""

from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model

from .models import Activity, DailySteps, WeightMeasurement

User = get_user_model()


def upsert_weight(
    user: User, recorded_at: datetime, weight_kg: Decimal | float, source: str = ""
) -> bool:
    """Crée ou met à jour la mesure de poids à cet instant. Renvoie `created`."""
    _, created = WeightMeasurement.objects.update_or_create(
        user=user,
        recorded_at=recorded_at,
        defaults={"weight_kg": weight_kg, "source": source},
    )
    return created


def upsert_daily_steps(user: User, on_date: date, steps: int) -> bool:
    """Remplace le total de pas du jour par `steps`. Renvoie `created`.

    Remplace plutôt qu'additionne : l'appelant (`health.importer`) a déjà
    sommé tous les intervalles du jour présents dans le fichier avant
    d'appeler cette fonction — réimporter le même export doit reproduire
    exactement le même total, pas le doubler.
    """
    _, created = DailySteps.objects.update_or_create(
        user=user, date=on_date, defaults={"steps": steps}
    )
    return created


def upsert_activity(
    user: User,
    activity_type: str,
    started_at: datetime,
    ended_at: datetime,
    *,
    duration_seconds: int | None = None,
    distance_meters: float | None = None,
    active_energy_kcal: float | None = None,
    average_heart_rate: int | None = None,
    source: str = "",
) -> bool:
    """Crée ou met à jour l'activité qui a débuté à cet instant. Renvoie `created`.

    `duration_seconds` est la durée active HealthKit (issue #79), distincte de
    `ended_at - started_at` qui inclut les pauses. Laissé à `None`, le modèle
    (`Activity.save`) se replie lui-même sur cet écart horaire — seule
    approximation disponible quand la source ne connaît pas la durée active
    (export sans l'attribut, ou données API #71 qui ne le transmettent pas).
    """
    _, created = Activity.objects.update_or_create(
        user=user,
        activity_type=activity_type,
        started_at=started_at,
        defaults={
            "ended_at": ended_at,
            "duration_seconds": duration_seconds,
            "distance_meters": distance_meters,
            "active_energy_kcal": active_energy_kcal,
            "average_heart_rate": average_heart_rate,
            "source": source,
        },
    )
    return created
