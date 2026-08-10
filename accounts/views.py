"""Comptes : premier démarrage, profil, gestion multi-utilisateurs."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from exercises.models import Exercise

from .forms import (
    EquipmentFormSet,
    FirstRunForm,
    ProfileForm,
    SelfRegistrationForm,
    StaffUserChangeForm,
    StaffUserCreationForm,
)
from .models import UserEquipment

User = get_user_model()

staff_required = user_passes_test(lambda user: user.is_staff)


def first_run(request: HttpRequest) -> HttpResponse:
    """Création du compte initial d'une installation neuve.

    Accessible uniquement tant qu'aucun utilisateur n'existe : une fois le
    premier compte créé, l'écran disparaît définitivement.
    """
    if User.objects.exists():
        return redirect("core:home")

    if request.method == "POST":
        form = FirstRunForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Compte créé. Bienvenue !")
            return redirect("core:home")
    else:
        form = FirstRunForm()

    return render(request, "accounts/first_run.html", {"form": form})


def register(request: HttpRequest) -> HttpResponse:
    """Inscription libre — désactivée par défaut (installation mono-utilisateur)."""
    if not settings.ALLOW_SELF_REGISTRATION:
        raise Http404("L'inscription libre est désactivée sur cette installation.")

    if request.user.is_authenticated:
        return redirect("core:home")

    if request.method == "POST":
        form = SelfRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Compte créé.")
            return redirect("accounts:profile")
    else:
        form = SelfRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    """Édition par l'utilisateur de ses informations et de ses mesures."""
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil enregistré.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=request.user)

    return render(request, "accounts/profile.html", {"form": form})


@login_required
def equipment(request: HttpRequest) -> HttpResponse:
    """Matériel possédé et charges disponibles.

    Sans cette déclaration, une séance ne peut ni écarter les exercices
    irréalisables ni proposer une charge qui existe vraiment.
    """
    queryset = UserEquipment.objects.filter(user=request.user)

    if request.method == "POST":
        formset = EquipmentFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            items = formset.save(commit=False)
            for item in items:
                item.user = request.user
                item.save()
            for item in formset.deleted_objects:
                item.delete()

            messages.success(request, "Matériel enregistré.")
            return redirect("accounts:equipment")
    else:
        formset = EquipmentFormSet(queryset=queryset)

    context = {
        "formset": formset,
        # Icône par matériel (issue #37) : une par valeur du référentiel, affichée ou
        # non selon la sélection en cours — voir `.ugg-equipment__icon` (CSS pur).
        "equipment_choices": Exercise.Equipment.choices,
    }
    return render(request, "accounts/equipment.html", context)


@login_required
@staff_required
def user_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "accounts/user_list.html",
        {"users": User.objects.order_by("-is_active", "email")},
    )


@login_required
@staff_required
def user_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = StaffUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Compte « {user.email} » créé.")
            return redirect("accounts:user_list")
    else:
        form = StaffUserCreationForm()

    return render(request, "accounts/user_form.html", {"form": form, "target": None})


@login_required
@staff_required
def user_update(request: HttpRequest, pk: int) -> HttpResponse:
    target = get_object_or_404(User, pk=pk)
    editing_self = target.pk == request.user.pk

    if request.method == "POST":
        form = StaffUserChangeForm(
            request.POST, request.FILES, instance=target, editing_self=editing_self
        )
        if form.is_valid():
            form.save()
            messages.success(request, f"Compte « {target.email} » enregistré.")
            return redirect("accounts:user_list")
    else:
        form = StaffUserChangeForm(instance=target, editing_self=editing_self)

    return render(request, "accounts/user_form.html", {"form": form, "target": target})
