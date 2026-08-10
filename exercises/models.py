"""Catalogue d'exercices : référentiel commun à tous les programmes.

Les données proviennent de `src/exercises.json` (free-exercise-db), dont les
valeurs sont en anglais. Les identifiants restent ceux du fichier — ils servent
de clé d'import stable — et les libellés affichés sont traduits ici.
"""

from django.conf import settings
from django.db import models


class Muscle(models.Model):
    """Groupe musculaire ciblé par un exercice.

    Table à part plutôt que liste dans l'exercice : la génération de programmes
    sélectionnera les exercices par muscle, et un filtre indexé vaut mieux
    qu'une recherche dans un document JSON.
    """

    slug = models.SlugField("identifiant", max_length=32, unique=True)
    name = models.CharField("nom", max_length=64)

    class Meta:
        verbose_name = "muscle"
        verbose_name_plural = "muscles"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Favorite(models.Model):
    """Exercice mis de côté par un utilisateur.

    Table de liaison explicite plutôt qu'un `ManyToManyField` nu : la date
    d'ajout permet de retrouver les derniers marqués, et la contrainte
    d'unicité rend le basculement idempotent — deux clics rapprochés ne
    créent pas deux lignes.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites"
    )
    exercise = models.ForeignKey("Exercise", on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField("ajouté le", auto_now_add=True)

    class Meta:
        verbose_name = "favori"
        verbose_name_plural = "favoris"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=["user", "exercise"], name="unique_favorite_per_user")
        ]

    def __str__(self) -> str:
        return f"{self.exercise} — {self.user}"


class Exercise(models.Model):
    """Exercice du référentiel.

    Un exercice est une donnée de catalogue, identique pour tous les
    utilisateurs : il n'appartient à personne et ne se modifie pas depuis
    l'interface. Un nouvel import met à jour les fiches existantes.
    """

    class Category(models.TextChoices):
        STRENGTH = "strength", "Renforcement"
        STRETCHING = "stretching", "Étirement"
        PLYOMETRICS = "plyometrics", "Pliométrie"
        POWERLIFTING = "powerlifting", "Force athlétique"
        OLYMPIC = "olympic weightlifting", "Haltérophilie"
        STRONGMAN = "strongman", "Strongman"
        CARDIO = "cardio", "Cardio"

    class Level(models.TextChoices):
        BEGINNER = "beginner", "Débutant"
        INTERMEDIATE = "intermediate", "Intermédiaire"
        EXPERT = "expert", "Confirmé"

    class Force(models.TextChoices):
        PUSH = "push", "Poussée"
        PULL = "pull", "Tirage"
        STATIC = "static", "Statique"

    class Mechanic(models.TextChoices):
        COMPOUND = "compound", "Polyarticulaire"
        ISOLATION = "isolation", "Isolation"

    class Equipment(models.TextChoices):
        BODY_ONLY = "body only", "Poids du corps"
        BARBELL = "barbell", "Barre"
        DUMBBELL = "dumbbell", "Haltères"
        KETTLEBELLS = "kettlebells", "Kettlebell"
        CABLE = "cable", "Poulie"
        MACHINE = "machine", "Machine"
        BANDS = "bands", "Élastiques"
        EZ_CURL_BAR = "e-z curl bar", "Barre EZ"
        MEDICINE_BALL = "medicine ball", "Médecine ball"
        EXERCISE_BALL = "exercise ball", "Ballon de gym"
        FOAM_ROLL = "foam roll", "Rouleau de massage"
        OTHER = "other", "Autre"

    slug = models.SlugField("identifiant", max_length=80, unique=True)
    name = models.CharField("nom", max_length=120)

    category = models.CharField("catégorie", max_length=24, choices=Category.choices)
    level = models.CharField("niveau", max_length=16, choices=Level.choices)

    # Facultatifs dans la source : une trentaine d'exercices n'ont pas de type
    # d'effort, et près d'une centaine pas de mécanique déclarée.
    force = models.CharField("type d'effort", max_length=8, choices=Force.choices, blank=True)
    mechanic = models.CharField("mécanique", max_length=12, choices=Mechanic.choices, blank=True)
    equipment = models.CharField("matériel", max_length=16, choices=Equipment.choices, blank=True)

    primary_muscles = models.ManyToManyField(
        Muscle, related_name="exercises_as_primary", verbose_name="muscles principaux", blank=True
    )
    secondary_muscles = models.ManyToManyField(
        Muscle,
        related_name="exercises_as_secondary",
        verbose_name="muscles secondaires",
        blank=True,
    )

    # Consignes ordonnées et chemins d'illustrations : listes lues telles quelles,
    # jamais filtrées ni jointes — un document convient mieux qu'une table.
    instructions = models.JSONField("consignes", default=list, blank=True)
    #: Traduction IA des consignes, vide tant qu'un rechargement traduit n'a pas
    #: eu lieu (issue #29). L'affichage retombe sur `instructions` en anglais.
    instructions_fr = models.JSONField("consignes (français)", default=list, blank=True)
    images = models.JSONField("illustrations", default=list, blank=True)

    class Meta:
        verbose_name = "exercice"
        verbose_name_plural = "exercices"
        ordering = ("name",)
        indexes = [
            models.Index(fields=["category", "level"]),
            models.Index(fields=["equipment"]),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def image_urls(self) -> list[str]:
        """Adresses des illustrations, vendorées sous le stockage média (issue #29)."""
        return [f"{settings.MEDIA_URL}exercises/{path}" for path in self.images]
