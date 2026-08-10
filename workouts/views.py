"""Séances : historique, composition, consultation."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from aiproviders.clients import get_active_client

from . import coaching, generator, timer
from .forms import WorkoutForm
from .models import Workout


@login_required
def workout_list(request: HttpRequest) -> HttpResponse:
    """Séances passées de l'utilisateur, la plus récente en tête.

    Même vue pour la page entière et, en HTMX, le seul bloc de résultats — voir
    exercises.views.exercise_list pour le même principe.
    """
    favorites_only = request.GET.get("favoris") == "1"

    workouts = Workout.objects.filter(user=request.user).prefetch_related("muscles")
    if favorites_only:
        workouts = workouts.filter(is_favorite=True)

    context = {"workouts": workouts, "favorites_only": favorites_only}

    if request.headers.get("HX-Request"):
        return render(request, "workouts/partials/workout_results.html", context)
    return render(request, "workouts/workout_list.html", context)


@login_required
def workout_create(request: HttpRequest) -> HttpResponse:
    """Composition d'une séance à partir des paramètres saisis."""
    if request.method == "POST":
        form = WorkoutForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                workout = generator.generate(
                    user=request.user,
                    duration_minutes=form.cleaned_data["duration_minutes"],
                    workout_format=form.cleaned_data["workout_format"],
                    muscles=[m.slug for m in form.cleaned_data["muscles"]],
                    favorites_ratio=form.cleaned_data["favorites_ratio"],
                    work_seconds=form.cleaned_data["work_seconds"],
                    rest_seconds=form.cleaned_data["rest_seconds"],
                    peak_reps=form.cleaned_data["peak_reps"],
                    equipment=form.cleaned_data.get("equipment"),
                )
            except generator.GenerationError as exc:
                # Le catalogue ne peut rien produire pour ces critères : c'est la
                # demande qu'il faut corriger, pas une panne à masquer.
                form.add_error(None, str(exc))
            else:
                return redirect("workouts:detail", pk=workout.pk)
    else:
        form = WorkoutForm(user=request.user)

    return render(request, "workouts/workout_form.html", {"form": form})


@login_required
def workout_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Déroulé d'une séance. Filtré sur l'utilisateur : une séance ne se partage pas."""
    workout = get_object_or_404(
        Workout.objects.prefetch_related("muscles", "items__exercise"),
        pk=pk,
        user=request.user,
    )
    context = {
        "workout": workout,
        # Bouton de traduction unitaire du rappel d'exercice (issue #31) :
        # un seul calcul par écran plutôt qu'un par exercice du déroulé.
        "can_translate": get_active_client() is not None,
        # Déroulé chronométré du minuteur de suivi (issue #35).
        "timeline": timer.build_timeline(workout),
    }
    return render(request, "workouts/workout_detail.html", context)


@login_required
def workout_coaching(request: HttpRequest, pk: int) -> HttpResponse:
    """Conseils du coach, chargés après la séance.

    En différé parce qu'un appel au fournisseur prend quelques secondes : la
    séance, elle, est prête tout de suite et ne doit pas attendre.
    """
    workout = get_object_or_404(Workout, pk=pk, user=request.user)
    notes = coaching.write_notes(workout)

    return render(request, "workouts/partials/coaching.html", {"notes": notes})


#: Doit rester égal à `max_length` du champ `Workout.name` — voir la troncature
#: défensive dans `workout_rename`.
NAME_MAX_LENGTH = 80


@login_required
@require_POST
def workout_rename(request: HttpRequest, pk: int) -> HttpResponse:
    """Renomme une séance. Un nom vide revient à l'intitulé du format.

    Pas de `Form` pour un seul champ facultatif : la longueur est tronquée
    défensivement plutôt que de faire échouer l'envoi pour un enjeu si faible.
    """
    workout = get_object_or_404(Workout, pk=pk, user=request.user)
    workout.name = request.POST.get("name", "").strip()[:NAME_MAX_LENGTH]
    workout.save(update_fields=["name"])

    if request.headers.get("HX-Request"):
        return render(request, "workouts/partials/name.html", {"workout": workout})
    return redirect("workouts:detail", pk=workout.pk)


@login_required
@require_POST
def workout_toggle_favorite(request: HttpRequest, pk: int) -> HttpResponse:
    """Bascule le favori d'une séance et rend le bouton dans son nouvel état."""
    workout = get_object_or_404(Workout, pk=pk, user=request.user)
    workout.is_favorite = not workout.is_favorite
    workout.save(update_fields=["is_favorite"])

    return render(
        request,
        "workouts/partials/favorite_button.html",
        {"workout": workout},
    )


@login_required
@require_POST
def workout_delete(request: HttpRequest, pk: int) -> HttpResponse:
    workout = get_object_or_404(Workout, pk=pk, user=request.user)
    workout.delete()
    messages.success(request, "Séance supprimée.")
    return redirect("workouts:list")
