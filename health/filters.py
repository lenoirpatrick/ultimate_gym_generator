"""Filtrage des activités affichées sur la page d'analyse (#73).

Deux critères, cumulés en ET, chacun avec sa propre sémantique :
- le type d'activité est à choix multiples (OU entre les valeurs cochées), en
  panneau repliable — patron d'`exercises.filters` ;
- la période est un choix fermé à une seule valeur (règle CLAUDE.md : un choix
  fermé passe par un contrôle segmenté `.ugg-segmented`, pas un `<details>`).
"""

from dataclasses import dataclass

from django.db.models import Q, QuerySet
from django.utils import timezone

from core.filtering import FilterGroup, Option, selected_values

from .models import Activity, DailySteps

TYPE_PARAM = "type"
PERIOD_PARAM = "periode"
#: Recherche texte libre, sur le type affiché et la source (issue #81). Se
#: cumule (ET) avec les autres critères, comme dans le catalogue d'exercices.
SEARCH_PARAM = "q"

#: (valeur, libellé, nombre de jours — `None` pour « tout »)
PERIOD_CHOICES: tuple[tuple[str, str, int | None], ...] = (
    ("7", "7 jours", 7),
    ("30", "30 jours", 30),
    ("90", "90 jours", 90),
    ("tout", "Tout", None),
)
DEFAULT_PERIOD = "30"


@dataclass(frozen=True)
class PeriodOption:
    value: str
    label: str
    selected: bool


_PERIOD_DAYS_BY_VALUE = {value: days for value, _label, days in PERIOD_CHOICES}


def selected_period(params) -> tuple[str, int | None]:
    """Période choisie, repliée sur la valeur par défaut si absente/inconnue."""
    value = params.get(PERIOD_PARAM, DEFAULT_PERIOD)
    if value not in _PERIOD_DAYS_BY_VALUE:
        value = DEFAULT_PERIOD
    return value, _PERIOD_DAYS_BY_VALUE[value]


def period_options(params) -> list[PeriodOption]:
    selected_value, _days = selected_period(params)
    return [
        PeriodOption(value=value, label=label, selected=value == selected_value)
        for value, label, _days in PERIOD_CHOICES
    ]


def build_type_group(params) -> FilterGroup:
    allowed = set(Activity.ActivityType.values)
    chosen = set(selected_values(params, TYPE_PARAM, allowed))
    return FilterGroup(
        name=TYPE_PARAM,
        legend="Type d'activité",
        options=[
            Option(value=value, label=label, selected=value in chosen)
            for value, label in Activity.ActivityType.choices
        ],
    )


def search_query(params) -> str:
    """Texte recherché, débarrassé des espaces superflus."""
    return params.get(SEARCH_PARAM, "").strip()


def filter_activities(params, user) -> QuerySet[Activity]:
    """Activités de `user` restreintes aux critères cochés."""
    queryset = Activity.objects.filter(user=user)

    _period_value, days = selected_period(params)
    if days is not None:
        cutoff = timezone.now() - timezone.timedelta(days=days)
        queryset = queryset.filter(started_at__gte=cutoff)

    types = selected_values(params, TYPE_PARAM, set(Activity.ActivityType.values))
    if types:
        queryset = queryset.filter(activity_type__in=types)

    query = search_query(params)
    if query:
        # Le type est stocké sous sa valeur HealthKit ("running"), pas son
        # libellé affiché ("Course à pied") : les codes dont le libellé
        # correspond sont résolus ici plutôt que recherchés en base.
        matching_types = [
            value
            for value, label in Activity.ActivityType.choices
            if query.lower() in label.lower()
        ]
        queryset = queryset.filter(Q(source__icontains=query) | Q(activity_type__in=matching_types))

    return queryset.order_by("-started_at")


def filter_daily_steps(params, user) -> QuerySet[DailySteps]:
    """Totaux de pas de `user` sur la période choisie (issue #75).

    Pas de critère de type ici : un total de pas n'a pas de type d'activité,
    seule la période s'applique.
    """
    queryset = DailySteps.objects.filter(user=user)

    _period_value, days = selected_period(params)
    if days is not None:
        cutoff = (timezone.now() - timezone.timedelta(days=days)).date()
        queryset = queryset.filter(date__gte=cutoff)

    return queryset.order_by("date")


def has_active_filters(type_group: FilterGroup, params) -> bool:
    value, _days = selected_period(params)
    return bool(type_group.selected_count) or value != DEFAULT_PERIOD or bool(search_query(params))
