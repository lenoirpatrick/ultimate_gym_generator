"""Vues du socle : accueil, sonde de santé, référentiel visuel."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

# Rôles sémantiques exposés par le référentiel visuel. Les valeurs vivent dans
# assets/css/tokens.css — on ne référence ici que les noms de variables.
COLOR_SWATCHES = (
    ("Surface", "--ugg-surface"),
    ("Surface haute", "--ugg-surface-raised"),
    ("Surface basse", "--ugg-surface-sunken"),
    ("Bordure", "--ugg-border"),
    ("Texte", "--ugg-text"),
    ("Texte discret", "--ugg-text-muted"),
    ("Accent", "--ugg-accent"),
    ("Succès", "--ugg-success"),
    ("Danger", "--ugg-danger"),
    ("Braise", "--ugg-ember-400"),
)


def home(request: HttpRequest) -> HttpResponse:
    return render(request, "core/home.html")


def healthz(request: HttpRequest) -> JsonResponse:
    """Sonde de santé consommée par Docker et par la CI.

    Vérifie que le processus répond *et* que la base est joignable : une
    application qui rend du HTML sans base n'est pas en bonne santé.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    # Capture volontairement large : toute panne côté base, quelle qu'en soit
    # la nature, doit dégrader la sonde plutôt que remonter une 500.
    except Exception as exc:
        return JsonResponse(
            {"status": "unhealthy", "database": "unreachable", "detail": str(exc)},
            status=503,
        )
    return JsonResponse({"status": "healthy", "database": "ok"})


def style_guide(request: HttpRequest) -> HttpResponse:
    """Référentiel visuel : tokens, composants, spinners.

    Réservé au développement — il expose des choix internes et n'a aucune
    raison d'être servi en production.
    """
    if not settings.DEBUG:
        raise Http404

    from exercises.filters import FilterGroup, Option
    from exercises.models import Exercise

    user_model = get_user_model()

    # Instances non enregistrées : la bascule s'illustre sans écrire en base.
    favorite_demos = [Exercise(pk=1, name="Non marqué"), Exercise(pk=2, name="Marqué")]
    favorite_demos[0].is_favorite = False
    favorite_demos[1].is_favorite = True
    return render(
        request,
        "core/style_guide.html",
        {
            "swatches": COLOR_SWATCHES,
            # Instances non enregistrées : le référentiel illustre le composant
            # sans dépendre du contenu de la base.
            "avatar_demos": [
                user_model(first_name="Alex", last_name="Martin"),
                user_model(email="coach@example.test"),
            ],
            "favorite_demos": favorite_demos,
            "filter_demos": [
                FilterGroup(
                    name="type",
                    legend="Type d'exercice",
                    options=[
                        Option(value, label, value == "cardio")
                        for value, label in Exercise.Category.choices
                    ],
                ),
                FilterGroup(
                    name="niveau",
                    legend="Niveau",
                    options=[
                        Option("beginner", "Débutant", True),
                        Option("intermediate", "Intermédiaire", True),
                        Option("expert", "Confirmé", False),
                    ],
                ),
                FilterGroup(
                    name="materiel",
                    legend="Matériel",
                    options=[
                        Option("barbell", "Barre", False),
                        Option("dumbbell", "Haltères", False),
                        Option("body only", "Poids du corps", False),
                    ],
                ),
            ],
        },
    )
