"""Filtrage du catalogue par niveau, effort, matériel et muscle.

Deux règles, celles qu'attend quiconque a déjà utilisé un filtre de boutique :
plusieurs valeurs d'un même critère s'additionnent (débutant **ou**
intermédiaire), tandis que deux critères se cumulent (débutant **et** à la
barre). Une valeur inconnue est ignorée plutôt que refusée — un lien partagé ne
doit pas casser parce que le référentiel a changé depuis.
"""

from django.db.models import Exists, OuterRef, Q, QuerySet

from core.filtering import FilterGroup, Option, selected_values

from .models import Exercise, Favorite, Muscle

__all__ = [
    "CHOICE_FILTERS",
    "FAVORITES_PARAM",
    "MUSCLE_PARAM",
    "SEARCH_PARAM",
    "FilterGroup",
    "Option",
    "build_groups",
    "favorites_only",
    "filter_exercises",
    "has_active_filters",
    "search_query",
    "selected_values",
]

#: Critères à valeurs fermées : paramètre de requête, champ, libellé, énumération.
#: Le type d'exercice vient en tête : c'est lui qui écarte le plus de catalogue
#: d'un seul geste — on ne cherche pas un étirement et un cardio dans la même
#: séance.
CHOICE_FILTERS: tuple[tuple[str, str, str, type], ...] = (
    ("type", "category", "Type d'exercice", Exercise.Category),
    ("niveau", "level", "Niveau", Exercise.Level),
    ("effort", "force", "Type d'effort", Exercise.Force),
    ("materiel", "equipment", "Matériel", Exercise.Equipment),
)

MUSCLE_PARAM = "muscle"

#: Critère à part : il ne porte qu'une case et dépend de l'utilisateur, là où
#: les autres se décrivent par une énumération fermée.
FAVORITES_PARAM = "favoris"

#: Recherche texte libre, sur le nom de l'exercice. Se cumule (ET) avec les
#: autres critères, comme n'importe lequel d'entre eux.
SEARCH_PARAM = "recherche"


def search_query(params) -> str:
    """Texte recherché, débarrassé des espaces superflus."""
    return params.get(SEARCH_PARAM, "").strip()


def build_groups(params) -> list[FilterGroup]:
    """Critères et options à afficher, avec les cases déjà cochées."""
    groups = []

    for name, _field, legend, choices in CHOICE_FILTERS:
        allowed = set(choices.values)
        chosen = set(selected_values(params, name, allowed))
        groups.append(
            FilterGroup(
                name=name,
                legend=legend,
                options=[
                    Option(value=value, label=label, selected=value in chosen)
                    for value, label in choices.choices
                ],
            )
        )

    muscles = list(Muscle.objects.all())
    chosen = set(selected_values(params, MUSCLE_PARAM, {muscle.slug for muscle in muscles}))
    groups.append(
        FilterGroup(
            name=MUSCLE_PARAM,
            legend="Muscle travaillé",
            options=[
                Option(value=muscle.slug, label=muscle.name, selected=muscle.slug in chosen)
                for muscle in muscles
            ],
        )
    )

    return groups


def favorites_only(params) -> bool:
    """Vrai lorsque la case « Mes favoris » est cochée."""
    return params.get(FAVORITES_PARAM) == "1"


def filter_exercises(params, user) -> QuerySet[Exercise]:
    """Catalogue restreint aux critères cochés, annoté de l'état « favori »."""
    marked = Favorite.objects.filter(user=user.pk, exercise=OuterRef("pk"))
    queryset = Exercise.objects.annotate(is_favorite=Exists(marked))

    query = search_query(params)
    if query:
        queryset = queryset.filter(name__icontains=query)

    if favorites_only(params):
        queryset = queryset.filter(is_favorite=True)

    for name, field, _legend, choices in CHOICE_FILTERS:
        values = selected_values(params, name, set(choices.values))
        if values:
            queryset = queryset.filter(**{f"{field}__in": values})

    muscles = selected_values(
        params, MUSCLE_PARAM, set(Muscle.objects.values_list("slug", flat=True))
    )
    if muscles:
        # « Travaillé » couvre les deux rôles : un exercice qui sollicite les
        # fessiers en second reste un exercice pour les fessiers. La jointure
        # multiplierait les lignes, d'où le `distinct`.
        queryset = queryset.filter(
            Q(primary_muscles__slug__in=muscles) | Q(secondary_muscles__slug__in=muscles)
        ).distinct()

    return queryset.prefetch_related("primary_muscles", "secondary_muscles")


def has_active_filters(groups: list[FilterGroup], params) -> bool:
    return (
        favorites_only(params)
        or bool(search_query(params))
        or any(group.selected_count for group in groups)
    )
