"""Indicateurs et séries de la page d'analyse (#72), calculés sur les activités
déjà restreintes par `health.filters.filter_activities` — KPI, graphiques et
liste affichée partagent le même filtrage, jamais deux logiques séparées.
"""

from dataclasses import dataclass, field
from datetime import timedelta

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, QuerySet, Sum
from django.db.models.functions import TruncWeek
from django.utils import timezone

from .models import Activity, DailySteps, WeightMeasurement

_DURATION = ExpressionWrapper(F("ended_at") - F("started_at"), output_field=DurationField())


@dataclass(frozen=True)
class Kpi:
    label: str
    value: str
    trend: str | None = None  # "up" | "down" | None
    trend_label: str = ""


@dataclass(frozen=True)
class ChartData:
    weight_labels: list[str] = field(default_factory=list)
    weight_values: list[float] = field(default_factory=list)
    volume_labels: list[str] = field(default_factory=list)
    volume_values: list[float] = field(default_factory=list)
    pace_labels: list[str] = field(default_factory=list)
    pace_values: list[float] = field(default_factory=list)
    steps_labels: list[str] = field(default_factory=list)
    steps_values: list[int] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "weight": {"labels": self.weight_labels, "values": self.weight_values},
            "volume": {"labels": self.volume_labels, "values": self.volume_values},
            "pace": {"labels": self.pace_labels, "values": self.pace_values},
            "steps": {"labels": self.steps_labels, "values": self.steps_values},
        }


def _format_duration(total: timedelta | None) -> str:
    if not total:
        return "0 min"
    minutes = int(total.total_seconds() // 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d}" if hours else f"{minutes} min"


def _weight_trend(user, latest: WeightMeasurement, days: int | None) -> tuple[str | None, str]:
    if days is None:
        reference = WeightMeasurement.objects.filter(user=user).order_by("recorded_at").first()
    else:
        cutoff = timezone.now() - timedelta(days=days)
        reference = (
            WeightMeasurement.objects.filter(user=user, recorded_at__lte=cutoff)
            .order_by("-recorded_at")
            .first()
        )

    if not reference or reference.pk == latest.pk:
        return None, "pas assez de recul pour une tendance"

    delta = latest.weight_kg - reference.weight_kg
    if delta == 0:
        return None, "stable sur la période"
    return ("up" if delta > 0 else "down"), f"{delta:+.1f} kg sur la période"


def build_kpis(
    user, activities: QuerySet[Activity], days: int | None, daily_steps: QuerySet[DailySteps]
) -> list[Kpi]:
    kpis = []

    latest_weight = WeightMeasurement.objects.filter(user=user).order_by("-recorded_at").first()
    if latest_weight:
        trend, trend_label = _weight_trend(user, latest_weight, days)
        kpis.append(
            Kpi(
                label="Poids actuel",
                value=f"{latest_weight.weight_kg} kg",
                trend=trend,
                trend_label=trend_label,
            )
        )
    else:
        kpis.append(Kpi(label="Poids actuel", value="—", trend_label="aucune mesure importée"))

    aggregates = activities.aggregate(
        count=Count("id"), total_duration=Sum(_DURATION), total_distance=Sum("distance_meters")
    )
    kpis.append(
        Kpi(
            label="Activités",
            value=str(aggregates["count"] or 0),
            trend_label=_format_duration(aggregates["total_duration"]),
        )
    )

    distance_km = (aggregates["total_distance"] or 0) / 1000
    kpis.append(Kpi(label="Distance parcourue", value=f"{distance_km:.1f} km"))

    runs = list(
        activities.filter(
            activity_type=Activity.ActivityType.RUNNING, distance_meters__isnull=False
        )
    )
    paces = [run.pace_seconds_per_km for run in runs if run.pace_seconds_per_km]
    if paces:
        average_pace = sum(paces) / len(paces)
        minutes, seconds = divmod(round(average_pace), 60)
        kpis.append(Kpi(label="Allure moyenne (course)", value=f"{minutes}:{seconds:02d} /km"))
    else:
        kpis.append(Kpi(label="Allure moyenne (course)", value="—", trend_label="aucune course"))

    steps_aggregates = daily_steps.aggregate(average=Avg("steps"), count=Count("id"))
    steps_days = steps_aggregates["count"]
    if steps_days:
        average_steps = f"{round(steps_aggregates['average']):,}".replace(",", " ")
        kpis.append(
            Kpi(
                label="Pas moyens (jour)",
                value=average_steps,
                trend_label=f"sur {steps_days} jour{'s' if steps_days > 1 else ''}",
            )
        )
    else:
        kpis.append(Kpi(label="Pas moyens (jour)", value="—", trend_label="aucun total importé"))

    return kpis


def build_chart_data(
    user, activities: QuerySet[Activity], days: int | None, daily_steps: QuerySet[DailySteps]
) -> ChartData:
    data = ChartData()

    weights_qs = WeightMeasurement.objects.filter(user=user).order_by("recorded_at")
    if days is not None:
        weights_qs = weights_qs.filter(recorded_at__gte=timezone.now() - timedelta(days=days))
    for measurement in weights_qs:
        data.weight_labels.append(measurement.recorded_at.strftime("%d/%m/%Y"))
        data.weight_values.append(float(measurement.weight_kg))

    weekly = (
        activities.annotate(week=TruncWeek("started_at"), duration=_DURATION)
        .values("week")
        .annotate(total_duration=Sum("duration"))
        .order_by("week")
    )
    for row in weekly:
        data.volume_labels.append(row["week"].strftime("%d/%m"))
        total: timedelta = row["total_duration"] or timedelta()
        data.volume_values.append(round(total.total_seconds() / 3600, 1))

    runs = activities.filter(
        activity_type=Activity.ActivityType.RUNNING, distance_meters__isnull=False
    ).order_by("started_at")
    for run in runs:
        pace = run.pace_seconds_per_km
        if not pace:
            continue
        data.pace_labels.append(run.started_at.strftime("%d/%m"))
        data.pace_values.append(round(pace / 60, 2))

    for entry in daily_steps:
        data.steps_labels.append(entry.date.strftime("%d/%m"))
        data.steps_values.append(entry.steps)

    return data
