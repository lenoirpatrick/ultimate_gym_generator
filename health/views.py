"""Import, API d'ingestion et gestion des clés API."""

import json
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import auth
from . import ingest as ingest_module
from .forms import ApiKeyForm, HealthImportForm
from .importer import ExportParseError, parse_export
from .models import Activity, ApiKey


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


@login_required
def api_keys(request: HttpRequest) -> HttpResponse:
    """Création et liste des clés API personnelles d'ingestion (#71)."""
    raw_key = None

    if request.method == "POST":
        form = ApiKeyForm(request.POST)
        if form.is_valid():
            _instance, raw_key = ApiKey.generate(request.user, form.cleaned_data["label"])
            form = ApiKeyForm()
    else:
        form = ApiKeyForm()

    return render(
        request,
        "health/api_keys.html",
        {
            "form": form,
            "raw_key": raw_key,
            "keys": ApiKey.objects.filter(user=request.user),
        },
    )


@login_required
@require_POST
def api_key_revoke(request: HttpRequest, pk: int) -> HttpResponse:
    """Supprime une clé API — action immédiate, confirmée côté gabarit (`hx-confirm`)."""
    key = get_object_or_404(ApiKey, pk=pk, user=request.user)
    key.delete()
    context = {"keys": ApiKey.objects.filter(user=request.user)}
    return render(request, "health/partials/api_key_rows.html", context)


@csrf_exempt
@require_POST
def ingest(request: HttpRequest) -> JsonResponse:
    """Point d'entrée POST d'ingestion à distance (#71), authentifié par clé API.

    Hors session : ni `@login_required` (rien à authentifier via cookie), ni
    protection CSRF (le jeton CSRF suppose une session, absente ici — la clé
    API en tient lieu). Une entrée invalide dans le lot n'empêche pas les
    autres d'être appliquées.
    """
    user = auth.authenticate_request(request)
    if user is None:
        return JsonResponse({"detail": "Clé API absente ou invalide."}, status=401)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "Corps de requête JSON invalide."}, status=400)

    weights_created = weights_updated = 0
    activities_created = activities_updated = 0
    errors: list[str] = []

    for index, entry in enumerate(payload.get("weights", [])):
        try:
            recorded_at = _parse_iso(entry["recorded_at"])
            created = ingest_module.upsert_weight(
                user, recorded_at, entry["weight_kg"], source=entry.get("source", "")
            )
            weights_created += created
            weights_updated += not created
        except (KeyError, ValueError, TypeError) as exc:
            errors.append(f"weights[{index}] : {exc}")

    for index, entry in enumerate(payload.get("activities", [])):
        try:
            activity_type = entry.get("activity_type", Activity.ActivityType.OTHER)
            if activity_type not in Activity.ActivityType.values:
                activity_type = Activity.ActivityType.OTHER
            created = ingest_module.upsert_activity(
                user,
                activity_type=activity_type,
                started_at=_parse_iso(entry["started_at"]),
                ended_at=_parse_iso(entry["ended_at"]),
                distance_meters=entry.get("distance_meters"),
                active_energy_kcal=entry.get("active_energy_kcal"),
                average_heart_rate=entry.get("average_heart_rate"),
                source=entry.get("source", ""),
            )
            activities_created += created
            activities_updated += not created
        except (KeyError, ValueError, TypeError) as exc:
            errors.append(f"activities[{index}] : {exc}")

    status = (
        400
        if errors
        and not (weights_created or weights_updated or activities_created or activities_updated)
        else 200
    )
    return JsonResponse(
        {
            "weights_created": weights_created,
            "weights_updated": weights_updated,
            "activities_created": activities_created,
            "activities_updated": activities_updated,
            "errors": errors,
        },
        status=status,
    )


def _parse_iso(raw: str) -> datetime:
    value = datetime.fromisoformat(raw)
    if timezone.is_naive(value):
        value = timezone.make_aware(value)
    return value
