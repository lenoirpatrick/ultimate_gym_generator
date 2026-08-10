"""Séances d'entraînement composées à partir du catalogue.

Une séance est enregistrée : elle porte les paramètres qui l'ont produite et le
détail de son déroulé. On la retrouve donc telle quelle à la salle, et son
adresse reste valable — ce qu'un simple affichage éphémère ne permettrait pas.
"""

from django.conf import settings
from django.db import models

from exercises.models import Exercise, Muscle


class Workout(models.Model):
    """Séance générée pour un utilisateur."""

    class Duration(models.IntegerChoices):
        """De 5 en 5 minutes, de 10 à 60 — la valeur par défaut est `THIRTY` (issue #32)."""

        TEN = 10, "10 minutes"
        FIFTEEN = 15, "15 minutes"
        TWENTY = 20, "20 minutes"
        TWENTY_FIVE = 25, "25 minutes"
        THIRTY = 30, "30 minutes"
        THIRTY_FIVE = 35, "35 minutes"
        FORTY = 40, "40 minutes"
        FORTY_FIVE = 45, "45 minutes"
        FIFTY = 50, "50 minutes"
        FIFTY_FIVE = 55, "55 minutes"
        SIXTY = 60, "60 minutes"

    class Format(models.TextChoices):
        HIIT = "hiit", "HIIT — intervalles intenses"
        TABATA = "tabata", "Tabata — 20 s / 10 s"
        CIRCUIT = "circuit", "Circuit training"
        PYRAMID = "pyramid", "Pyramide"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workouts"
    )
    created_at = models.DateTimeField("créée le", auto_now_add=True)

    #: Facultatif : deux séances du même format sont sinon indiscernables dans
    #: l'historique. Vide, l'intitulé de secours reste le format — voir
    #: `display_name`.
    name = models.CharField("nom", max_length=80, blank=True)

    duration_minutes = models.PositiveSmallIntegerField("durée", choices=Duration.choices)
    format = models.CharField("type de travail", max_length=12, choices=Format.choices)
    muscles = models.ManyToManyField(Muscle, verbose_name="parties du corps", blank=True)

    favorites_ratio = models.PositiveSmallIntegerField(
        "part de favoris",
        default=25,
        help_text="Pourcentage d'exercices puisés dans les favoris.",
    )

    #: Temps demandés à la composition. Conservés même quand le format ne les
    #: retient pas tous (la pyramide n'utilise que le repos) : une séance
    #: rouverte doit dire avec quels réglages elle a été composée.
    work_seconds = models.PositiveSmallIntegerField("effort demandé (s)", null=True, blank=True)
    rest_seconds = models.PositiveSmallIntegerField("repos demandé (s)", null=True, blank=True)

    #: Durée réellement occupée par le déroulé. Elle n'atteint pas toujours la
    #: durée demandée : un format se remplit par blocs entiers.
    planned_seconds = models.PositiveIntegerField("durée planifiée", default=0)

    #: Séance mise de côté. Table à part écartée volontairement : une séance
    #: n'a ni la variété ni le volume d'un catalogue d'exercices, un simple
    #: booléen suffit à la retrouver dans l'historique.
    is_favorite = models.BooleanField("favori", default=False)

    #: Rédigés par l'IA après coup, et mémorisés pour ne pas rappeler le
    #: fournisseur à chaque consultation.
    coaching_notes = models.TextField("conseils", blank=True)

    class Meta:
        verbose_name = "séance"
        verbose_name_plural = "séances"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.get_format_display()} — {self.duration_minutes} min"

    @property
    def display_name(self) -> str:
        """Nom choisi par l'utilisateur, ou l'intitulé du format à défaut."""
        return self.name or self.get_format_display()

    @property
    def planned_minutes(self) -> int:
        return round(self.planned_seconds / 60)

    def blocks(self) -> list[dict]:
        """Déroulé regroupé par bloc, tel que l'affiche l'écran de séance."""
        grouped: dict[int, dict] = {}
        for item in self.items.all():
            block = grouped.setdefault(
                item.block_index,
                {"index": item.block_index, "label": item.block_label, "items": []},
            )
            block["items"].append(item)
        return list(grouped.values())


class WorkoutExercise(models.Model):
    """Un exercice dans le déroulé d'une séance, avec sa prescription.

    Le bloc est un simple entier porté par la ligne plutôt qu'une table de plus :
    seul l'affichage a besoin du regroupement.
    """

    workout = models.ForeignKey(Workout, on_delete=models.CASCADE, related_name="items")
    position = models.PositiveSmallIntegerField("position")

    block_index = models.PositiveSmallIntegerField("bloc", default=0)
    block_label = models.CharField("intitulé du bloc", max_length=60, blank=True)

    # PROTECT : réimporter le catalogue ne doit pas vider une séance passée.
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name="+")

    rounds = models.PositiveSmallIntegerField("séries", null=True, blank=True)
    work_seconds = models.PositiveSmallIntegerField("effort (s)", null=True, blank=True)
    rest_seconds = models.PositiveSmallIntegerField("repos (s)", null=True, blank=True)

    #: Répétitions série par série ; vide pour un exercice chronométré.
    reps = models.JSONField("répétitions", default=list, blank=True)

    #: Charges série par série. Une seule valeur pour un exercice à charge
    #: constante, autant que de séries en pyramide — où la charge monte quand
    #: les répétitions descendent.
    loads = models.JSONField("charges (kg)", default=list, blank=True)

    class Meta:
        verbose_name = "exercice de séance"
        verbose_name_plural = "exercices de séance"
        ordering = ("position",)

    def __str__(self) -> str:
        return f"{self.position}. {self.exercise}"

    @property
    def is_timed(self) -> bool:
        return bool(self.work_seconds)

    @property
    def load_summary(self) -> str:
        """Charge à afficher : une valeur, ou la plage parcourue en pyramide."""
        if not self.loads:
            return ""
        low, high = min(self.loads), max(self.loads)
        if low == high:
            return f"{low:g} kg"
        return f"{low:g} → {high:g} kg"
