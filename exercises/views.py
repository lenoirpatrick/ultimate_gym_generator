"""Amorçage du catalogue d'exercices.

L'import est découpé en tranches pilotées par le navigateur : chaque réponse
HTMX renvoie l'avancement et déclenche la tranche suivante. La progression
affichée est donc réelle — elle mesure ce qui est en base — et aucun thread ni
cache partagé n'est nécessaire pour la connaître.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import catalog


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
