"""Amorçage du catalogue d'exercices.

L'import est découpé en tranches pilotées par le navigateur : chaque réponse
HTMX renvoie l'avancement et déclenche la tranche suivante. La progression
affichée est donc réelle — elle mesure ce qui est en base — et aucun thread ni
cache partagé n'est nécessaire pour la connaître.
"""

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import catalog, filters
from .models import Exercise, Favorite

#: Cartes par page. Assez pour remplir un grand écran, assez peu pour qu'un
#: téléphone ne charge pas 873 fiches d'un coup.
PAGE_SIZE = 24


@login_required
def exercise_list(request: HttpRequest) -> HttpResponse:
    """Catalogue filtrable.

    La même vue sert la page entière et, en HTMX, le seul bloc de résultats :
    l'adresse porte donc toujours les critères cochés, ce qui rend une sélection
    partageable et rechargeable.
    """
    return _render_catalog(request, request.GET)


@login_required
def favorite_list(request: HttpRequest) -> HttpResponse:
    """Catalogue restreint aux favoris.

    Même écran que le catalogue, critère « Mes favoris » imposé : une adresse
    qu'on garde en marque-page, plutôt qu'une case à recocher à chaque visite.
    """
    params = request.GET.copy()
    params[filters.FAVORITES_PARAM] = "1"
    return _render_catalog(request, params, favorites_page=True)


def _render_catalog(request: HttpRequest, params, favorites_page: bool = False) -> HttpResponse:
    groups = filters.build_groups(params)
    queryset = filters.filter_exercises(params, request.user).order_by("name")

    page = Paginator(queryset, PAGE_SIZE).get_page(params.get("page"))

    context = {
        "groups": groups,
        "page": page,
        "total": Exercise.objects.count(),
        "filtered": filters.has_active_filters(groups, params),
        "favorites_only": filters.favorites_only(params),
        "search_query": filters.search_query(params),
        "favorites_page": favorites_page,
        # Les liens du bloc de résultats doivent rester sur l'écran courant :
        # « Tout effacer » depuis les favoris ne renvoie pas au catalogue entier.
        "base_url": reverse("exercises:favorites" if favorites_page else "exercises:list"),
        "query": _query_without_page(params),
    }

    if request.headers.get("HX-Request"):
        # Les compteurs de critères accompagnent la réponse en échange
        # hors-bande ; à la première charge, ils sont déjà dans le formulaire.
        return render(request, "exercises/partials/results.html", context | {"oob": True})
    return render(request, "exercises/exercise_list.html", context)


@login_required
@require_POST
def toggle_favorite(request: HttpRequest, pk: int) -> HttpResponse:
    """Ajoute ou retire un favori, et rend le bouton dans son nouvel état."""
    exercise = get_object_or_404(Exercise, pk=pk)

    favorite, created = Favorite.objects.get_or_create(user=request.user, exercise=exercise)
    if not created:
        favorite.delete()

    exercise.is_favorite = created
    return render(
        request,
        "exercises/partials/favorite_button.html",
        {"exercise": exercise},
    )


def _query_without_page(params) -> str:
    """Critères sérialisés sans le numéro de page, pour construire les liens de pagination."""
    remaining = params.copy()
    remaining.pop("page", None)
    return remaining.urlencode()


@login_required
def loading(request: HttpRequest) -> HttpResponse:
    """Écran d'attente affiché tant que le catalogue n'est pas en base."""
    if catalog.is_loaded():
        return redirect("core:home")

    return render(request, "exercises/loading.html", _state(offset=0))


@login_required
@require_POST
def load_batch(request: HttpRequest) -> HttpResponse:
    """Importe une tranche et rend la barre, qui déclenchera la suivante."""
    offset = _offset(request.POST.get("offset"))

    try:
        reached = catalog.import_batch(offset)
    except catalog.CatalogError as exc:
        return render(request, "exercises/partials/progress.html", {"error": str(exc)})

    return render(request, "exercises/partials/progress.html", _state(offset=reached))


def _offset(raw: str | None) -> int:
    """Position transmise par le fragment précédent, jamais lue telle quelle."""
    try:
        return max(0, int(raw or 0))
    except ValueError:
        return 0


def _state(offset: int) -> dict:
    progress = catalog.progress()
    return {
        "progress": progress,
        "offset": offset,
        "detail": f"{progress.imported} / {progress.total}",
        "error": None,
    }
