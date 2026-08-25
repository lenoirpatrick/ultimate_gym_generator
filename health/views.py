"""Import des données de santé."""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .forms import HealthImportForm
from .importer import ExportParseError, parse_export


@login_required
def import_view(request: HttpRequest) -> HttpResponse:
    """Import synchrone d'un export Apple Health (#70).

    Contrairement au chargement du catalogue d'exercices, ce n'est pas une
    tranche par appel HTMX (voir `health.importer` pour le pourquoi) : la
    requête POST traite le fichier entier et rend directement le résultat.
    """
    if request.method == "POST":
        result = None
        error = None
        form = HealthImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                result = parse_export(request.user, form.cleaned_data["file"])
            except ExportParseError as exc:
                error = str(exc)
        context = {"form": form, "result": result, "error": error}
        return render(request, "health/partials/import_panel.html", context)

    form = HealthImportForm()
    return render(request, "health/import.html", {"form": form, "result": None, "error": None})
