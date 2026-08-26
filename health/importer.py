"""Lecture d'un export Apple Health (`export.xml`).

Contrairement au catalogue d'exercices — un petit JSON versionné, ré-échantillonnable
par tranches (`exercises.catalog`) — un export Apple Health est un unique fichier XML
à parcourir séquentiellement, potentiellement volumineux. Le re-parcourir par
tranches à chaque appel HTMX coûterait un balayage complet à chaque tranche (O(n²)) ;
l'import se fait donc en une seule passe, dans une seule requête (voir
`health.views.import_view`), bornée par `settings.APPLE_HEALTH_IMPORT_MAX_BYTES`.

Le parsing passe par `defusedxml` plutôt que `xml.etree` directement : un fichier
déposé par l'utilisateur reste une entrée non fiable, et `xml.etree` ne se protège
pas par défaut des attaques XML classiques (entités externes, expansion
d'entités). `defusedxml.ElementTree.iterparse` a la même interface, entités
interdites en plus. Chaque `<Record>`/`<Workout>` traité est vidé (`elem.clear()`)
pour ne pas garder tout le fichier en mémoire.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime

import defusedxml.ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from . import ingest
from .models import Activity

#: Poids : identifiant du record HealthKit et facteurs de conversion vers le kg.
BODY_MASS_TYPE = "HKQuantityTypeIdentifierBodyMass"
WEIGHT_UNIT_TO_KG = {"kg": 1.0, "kgs": 1.0, "lb": 0.45359237, "lbs": 0.45359237}

#: Pas (issue #75) : exportés par petits intervalles, jamais un total par
#: jour — agrégés en mémoire pendant le parcours, écrits une fois à la fin.
STEP_COUNT_TYPE = "HKQuantityTypeIdentifierStepCount"

#: Distance : identifiants HealthKit possibles et facteurs de conversion vers le mètre.
DISTANCE_TYPES = (
    "HKQuantityTypeIdentifierDistanceWalkingRunning",
    "HKQuantityTypeIdentifierDistanceCycling",
    "HKQuantityTypeIdentifierDistanceSwimming",
)
DISTANCE_UNIT_TO_M = {"km": 1000.0, "mi": 1609.344, "m": 1.0, "yd": 0.9144}

ACTIVE_ENERGY_TYPE = "HKQuantityTypeIdentifierActiveEnergyBurned"
ENERGY_UNIT_TO_KCAL = {"kcal": 1.0, "Cal": 1.0, "kJ": 1 / 4.184}

HEART_RATE_TYPE = "HKQuantityTypeIdentifierHeartRate"

#: Types d'activité HealthKit couverts explicitement ; un type absent de cette
#: table est importé tout de même, classé `OTHER` — traiter la donnée comme un
#: coach professionnel ne consiste pas à en jeter une partie silencieusement.
WORKOUT_TYPE_MAP = {
    "HKWorkoutActivityTypeRunning": Activity.ActivityType.RUNNING,
    "HKWorkoutActivityTypeWalking": Activity.ActivityType.WALKING,
    "HKWorkoutActivityTypeCycling": Activity.ActivityType.CYCLING,
    "HKWorkoutActivityTypeSwimming": Activity.ActivityType.SWIMMING,
    "HKWorkoutActivityTypeHiking": Activity.ActivityType.HIKING,
    "HKWorkoutActivityTypeTraditionalStrengthTraining": Activity.ActivityType.STRENGTH_TRAINING,
    "HKWorkoutActivityTypeFunctionalStrengthTraining": Activity.ActivityType.STRENGTH_TRAINING,
    "HKWorkoutActivityTypeRowing": Activity.ActivityType.ROWING,
    "HKWorkoutActivityTypeElliptical": Activity.ActivityType.ELLIPTICAL,
    "HKWorkoutActivityTypeYoga": Activity.ActivityType.YOGA,
}


class ExportParseError(Exception):
    """Le fichier fourni n'est pas un export Apple Health exploitable."""


@dataclass
class ImportResult:
    weights_created: int = 0
    weights_updated: int = 0
    activities_created: int = 0
    activities_updated: int = 0
    daily_steps_created: int = 0
    daily_steps_updated: int = 0
    skipped_types: set[str] = field(default_factory=set)
    #: Enregistrements antérieurs à `since` (issue #74), écartés sans erreur.
    skipped_before_since: int = 0

    @property
    def total(self) -> int:
        return (
            self.weights_created
            + self.weights_updated
            + self.activities_created
            + self.activities_updated
            + self.daily_steps_created
            + self.daily_steps_updated
        )


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        return None


def _record_weight_kg(attrib: dict) -> float | None:
    try:
        value = float(attrib["value"])
    except (KeyError, ValueError):
        return None
    factor = WEIGHT_UNIT_TO_KG.get(attrib.get("unit", "kg"))
    return value * factor if factor else None


def _record_steps(attrib: dict) -> float | None:
    try:
        return float(attrib["value"])
    except (KeyError, ValueError):
        return None


def _workout_statistics(elem: ET.Element) -> dict[str, dict]:
    """Statistiques imbriquées d'un `<Workout>`, indexées par type HealthKit.

    Les exports récents ne portent plus la distance/l'énergie en attribut
    direct du `<Workout>` mais dans ces `<WorkoutStatistics>` enfants.
    """
    return {stat.get("type"): stat.attrib for stat in elem.findall("WorkoutStatistics")}


def _workout_distance_meters(elem: ET.Element, stats: dict[str, dict]) -> float | None:
    unit = elem.get("totalDistanceUnit")
    value = elem.get("totalDistance")
    if value is None:
        for distance_type in DISTANCE_TYPES:
            stat = stats.get(distance_type)
            if stat and stat.get("sum") is not None:
                value, unit = stat["sum"], stat.get("unit")
                break
    if value is None:
        return None
    factor = DISTANCE_UNIT_TO_M.get(unit or "km")
    try:
        return float(value) * factor if factor else None
    except ValueError:
        return None


def _workout_energy_kcal(elem: ET.Element, stats: dict[str, dict]) -> float | None:
    unit = elem.get("totalEnergyBurnedUnit")
    value = elem.get("totalEnergyBurned")
    if value is None:
        stat = stats.get(ACTIVE_ENERGY_TYPE)
        if stat and stat.get("sum") is not None:
            value, unit = stat["sum"], stat.get("unit")
    if value is None:
        return None
    factor = ENERGY_UNIT_TO_KCAL.get(unit or "kcal")
    try:
        return float(value) * factor if factor else None
    except ValueError:
        return None


def _workout_average_heart_rate(stats: dict[str, dict]) -> int | None:
    stat = stats.get(HEART_RATE_TYPE)
    if not stat or stat.get("average") is None:
        return None
    try:
        return round(float(stat["average"]))
    except ValueError:
        return None


def parse_export(user, file, since: date | None = None) -> ImportResult:
    """Importe un export Apple Health pour `user`. Lève `ExportParseError` si illisible.

    `since` (issue #74) borne l'import aux enregistrements à partir de cette
    date — utile pour un export volumineux (plusieurs années d'historique) où
    seule une période récente intéresse l'utilisateur, sans avoir à relever le
    plafond `APPLE_HEALTH_IMPORT_MAX_BYTES` pour autant : la taille du fichier
    déposé ne change pas, seul ce qui en est retenu diminue.
    """
    result = ImportResult()
    steps_by_date: dict[date, float] = {}

    try:
        elements = SafeET.iterparse(file, events=("end",))
        for _, elem in elements:
            if elem.tag == "Record" and elem.get("type") == STEP_COUNT_TYPE:
                started_at = _parse_date(elem.get("startDate"))
                if started_at is not None and since is not None and started_at.date() < since:
                    result.skipped_before_since += 1
                    elem.clear()
                    continue

                steps = _record_steps(elem.attrib)
                if started_at is not None and steps is not None:
                    day = started_at.date()
                    steps_by_date[day] = steps_by_date.get(day, 0) + steps
                elem.clear()

            elif elem.tag == "Record" and elem.get("type") == BODY_MASS_TYPE:
                started_at = _parse_date(elem.get("startDate"))
                if started_at is not None and since is not None and started_at.date() < since:
                    result.skipped_before_since += 1
                    elem.clear()
                    continue

                weight_kg = _record_weight_kg(elem.attrib)
                if started_at is not None and weight_kg is not None:
                    created = ingest.upsert_weight(
                        user, started_at, round(weight_kg, 2), source=elem.get("sourceName", "")
                    )
                    if created:
                        result.weights_created += 1
                    else:
                        result.weights_updated += 1
                elem.clear()

            elif elem.tag == "Workout":
                started_at = _parse_date(elem.get("startDate"))
                if started_at is not None and since is not None and started_at.date() < since:
                    result.skipped_before_since += 1
                    elem.clear()
                    continue

                ended_at = _parse_date(elem.get("endDate"))
                raw_type = elem.get("workoutActivityType", "")
                activity_type = WORKOUT_TYPE_MAP.get(raw_type)
                if activity_type is None:
                    activity_type = Activity.ActivityType.OTHER
                    result.skipped_types.add(raw_type)

                if started_at is not None and ended_at is not None:
                    stats = _workout_statistics(elem)
                    created = ingest.upsert_activity(
                        user,
                        activity_type=activity_type,
                        started_at=started_at,
                        ended_at=ended_at,
                        distance_meters=_workout_distance_meters(elem, stats),
                        active_energy_kcal=_workout_energy_kcal(elem, stats),
                        average_heart_rate=_workout_average_heart_rate(stats),
                        source=elem.get("sourceName", ""),
                    )
                    if created:
                        result.activities_created += 1
                    else:
                        result.activities_updated += 1
                elem.clear()
    except (ET.ParseError, DefusedXmlException) as exc:
        raise ExportParseError(
            "Le fichier n'est pas un export Apple Health valide (XML illisible ou dangereux)."
        ) from exc

    for day, steps in steps_by_date.items():
        created = ingest.upsert_daily_steps(user, day, round(steps))
        if created:
            result.daily_steps_created += 1
        else:
            result.daily_steps_updated += 1

    return result
