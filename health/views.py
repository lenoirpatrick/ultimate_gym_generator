"""Import, API d'ingestion, gestion des clés API et page d'analyse."""

import json
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import analytics, auth, exclusions, filters
from . import ingest as ingest_module
from .forms import ActivityTypeForm, ApiKeyForm, HealthImportForm
from .importer import ExportParseError, parse_export
from .models import Activity, ApiKey, DailySteps, WeightMeasurement


def _dashboard_context(user, params) -> dict:
    """Contexte des résultats de l'analyse (#72, #73), pour la page comme pour
    les actions qui la modifient depuis place (suppression/édition, #81) —
    une seule construction, jamais recalculée différemment selon l'appelant.
    """
    type_group = filters.build_type_group(params)
    activities = filters.filter_activities(params, user)
    daily_steps = filters.filter_daily_steps(params, user)
    _period_value, days = filters.selected_period(params)
    chart_data = analytics.build_chart_data(user, activities, days, daily_steps)

    return {
        "type_group": type_group,
        "period_options": filters.period_options(params),
        "search_query": filters.search_query(params),
        "filtered": filters.has_active_filters(type_group, params),
        "activities": activities[:50],
        "activity_type_choices": Activity.ActivityType.choices,
        "kpis": analytics.build_kpis(user, activities, days, daily_steps),
        # Objet pour masquer les graphiques sans série (issue #84) ; dict pour
        # le JSON lu par health_charts.js — deux formes du même calcul,
        # jamais deux logiques séparées.
        "charts": chart_data,
        "chart_data": chart_data.as_dict(),
        "has_data": WeightMeasurement.objects.filter(user=user).exists()
        or Activity.objects.filter(user=user).exists()
        or DailySteps.objects.filter(user=user).exists(),
        "base_url": reverse("health:dashboard"),
    }


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Page d'analyse : KPI, graphiques et activités, filtrables (#72, #73)."""
    context = _dashboard_context(request.user, request.GET)

    if request.headers.get("HX-Request"):
        return render(request, "health/partials/dashboard_results.html", context)
    return render(request, "health/dashboard.html", context)


@login_required
@require_POST
def activity_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Supprime une activité et l'exclut définitivement du réimport (issue #81).

    Les critères courants (période, type, recherche) voyagent dans le corps
    de la requête via `hx-include` sur le formulaire de filtre — la vue rend
    donc la même vue filtrée qu'avant la suppression, pas la liste entière.
    """
    activity = get_object_or_404(Activity, pk=pk, user=request.user)
    exclusions.exclude_activity(request.user, activity.activity_type, activity.started_at)
    activity.delete()

    context = _dashboard_context(request.user, request.POST)
    return render(request, "health/partials/dashboard_results.html", context)


@login_required
@require_POST
def activity_edit_type(request: HttpRequest, pk: int) -> HttpResponse:
    """Modifie le type d'une activité (issue #81).

    Le type fait partie de la clé naturelle d'upsert : le changer déplace
    l'activité vers une nouvelle clé. Sans exclure l'**ancienne**, un
    réimport la recréerait telle quelle à côté de la version corrigée.
    """
    activity = get_object_or_404(Activity, pk=pk, user=request.user)
    form = ActivityTypeForm(request.POST)
    if form.is_valid():
        exclusions.exclude_activity(request.user, activity.activity_type, activity.started_at)
        activity.activity_type = form.cleaned_data["activity_type"]
        activity.save(update_fields=["activity_type"])

    context = _dashboard_context(request.user, request.POST)
    return render(request, "health/partials/dashboard_results.html", context)


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
                result = parse_export(
                    request.user, form.cleaned_data["file"], since=form.cleaned_data["since"]
                )
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

    weights_created = weights_updated = weights_excluded = 0
    activities_created = activities_updated = activities_excluded = 0
    errors: list[str] = []

    for index, entry in enumerate(payload.get("weights", [])):
        try:
            recorded_at = _parse_iso(entry["recorded_at"])
            created = ingest_module.upsert_weight(
                user, recorded_at, entry["weight_kg"], source=entry.get("source", "")
            )
            if created is None:
                weights_excluded += 1
            elif created:
                weights_created += 1
            else:
                weights_updated += 1
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
                duration_seconds=entry.get("duration_seconds"),
                distance_meters=entry.get("distance_meters"),
                active_energy_kcal=entry.get("active_energy_kcal"),
                average_heart_rate=entry.get("average_heart_rate"),
                source=entry.get("source", ""),
            )
            if created is None:
                activities_excluded += 1
            elif created:
                activities_created += 1
            else:
                activities_updated += 1
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
            "weights_excluded": weights_excluded,
            "activities_created": activities_created,
            "activities_updated": activities_updated,
            "activities_excluded": activities_excluded,
            "errors": errors,
        },
        status=status,
    )


def _parse_iso(raw: str) -> datetime:
    value = datetime.fromisoformat(raw)
    if timezone.is_naive(value):
        value = timezone.make_aware(value)
    return value
