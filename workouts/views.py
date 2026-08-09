"""Séances : historique, composition, consultation."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import UserEquipment

from . import generator
from .forms import WorkoutForm
from .models import Workout


@login_required
def workout_list(request: HttpRequest) -> HttpResponse:
    """Séances passées de l'utilisateur, la plus récente en tête."""
    workouts = Workout.objects.filter(user=request.user).prefetch_related("muscles")
    return render(request, "workouts/workout_list.html", {"workouts": workouts})


@login_required
def workout_create(request: HttpRequest) -> HttpResponse:
    """Composition d'une séance à partir des paramètres saisis."""
    equipment = UserEquipment.objects.filter(user=request.user)

    if request.method == "POST":
        form = WorkoutForm(request.POST)
        if form.is_valid():
            try:
                workout = generator.generate(
                    user=request.user,
                    duration_minutes=form.cleaned_data["duration_minutes"],
                    workout_format=form.cleaned_data["workout_format"],
                    muscles=[m.slug for m in form.cleaned_data["muscles"]],
                    favorites_ratio=form.cleaned_data["favorites_ratio"],
                )
            except generator.GenerationError as exc:
                # Le catalogue ne peut rien produire pour ces critères : c'est la
                # demande qu'il faut corriger, pas une panne à masquer.
                form.add_error(None, str(exc))
            else:
                return redirect("workouts:detail", pk=workout.pk)
    else:
        form = WorkoutForm()

    return render(
        request,
        "workouts/workout_form.html",
        {"form": form, "equipment": equipment},
    )


@login_required
def workout_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Déroulé d'une séance. Filtré sur l'utilisateur : une séance ne se partage pas."""
    workout = get_object_or_404(
        Workout.objects.prefetch_related("muscles", "items__exercise"),
        pk=pk,
        user=request.user,
    )
    return render(request, "workouts/workout_detail.html", {"workout": workout})


@login_required
@require_POST
def workout_delete(request: HttpRequest, pk: int) -> HttpResponse:
    workout = get_object_or_404(Workout, pk=pk, user=request.user)
    workout.delete()
    messages.success(request, "Séance supprimée.")
    return redirect("workouts:list")
