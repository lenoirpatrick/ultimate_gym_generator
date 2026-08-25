"""Données de santé importées depuis Apple HealthKit.

Un export Apple Health classique ne porte aucun identifiant stable par
enregistrement — contrairement au catalogue d'exercices, qui a un `slug`.
L'unicité s'appuie donc sur une clé naturelle : l'instant de la mesure pour un
poids, le début de l'activité pour une séance. Un réimport met donc à jour la
ligne existante plutôt que d'en créer une seconde (issue #70).
"""

from django.conf import settings
from django.db import models


class WeightMeasurement(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weight_measurements",
        verbose_name="utilisateur",
    )
    recorded_at = models.DateTimeField("mesurée le")
    weight_kg = models.DecimalField("poids (kg)", max_digits=5, decimal_places=2)
    source = models.CharField("source", max_length=120, blank=True)

    class Meta:
        verbose_name = "mesure de poids"
        verbose_name_plural = "mesures de poids"
        ordering = ("-recorded_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["user", "recorded_at"], name="unique_weight_per_instant"
            )
        ]

    def __str__(self) -> str:
        return f"{self.weight_kg} kg — {self.recorded_at:%d/%m/%Y}"


class Activity(models.Model):
    class ActivityType(models.TextChoices):
        RUNNING = "running", "Course à pied"
        WALKING = "walking", "Marche"
        CYCLING = "cycling", "Vélo"
        SWIMMING = "swimming", "Natation"
        HIKING = "hiking", "Randonnée"
        STRENGTH_TRAINING = "strength_training", "Musculation"
        ROWING = "rowing", "Aviron"
        ELLIPTICAL = "elliptical", "Vélo elliptique"
        YOGA = "yoga", "Yoga"
        OTHER = "other", "Autre"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activities",
        verbose_name="utilisateur",
    )
    activity_type = models.CharField(
        "type", max_length=24, choices=ActivityType.choices, default=ActivityType.OTHER
    )
    started_at = models.DateTimeField("débutée le")
    ended_at = models.DateTimeField("terminée le")
    distance_meters = models.FloatField("distance (m)", null=True, blank=True)
    active_energy_kcal = models.FloatField("énergie active (kcal)", null=True, blank=True)
    average_heart_rate = models.PositiveSmallIntegerField("FC moyenne (bpm)", null=True, blank=True)
    source = models.CharField("source", max_length=120, blank=True)

    class Meta:
        verbose_name = "activité"
        verbose_name_plural = "activités"
        ordering = ("-started_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["user", "activity_type", "started_at"], name="unique_activity_start"
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_activity_type_display()} — {self.started_at:%d/%m/%Y}"

    @property
    def duration_seconds(self) -> int:
        return max(0, int((self.ended_at - self.started_at).total_seconds()))

    @property
    def duration_label(self) -> str:
        hours, minutes = divmod(self.duration_seconds // 60, 60)
        return f"{hours} h {minutes:02d}" if hours else f"{minutes} min"

    @property
    def distance_km_label(self) -> str | None:
        if not self.distance_meters:
            return None
        return f"{self.distance_meters / 1000:.1f} km"

    @property
    def pace_seconds_per_km(self) -> float | None:
        """Allure moyenne, pertinente seulement pour une activité avec distance."""
        if not self.distance_meters:
            return None
        return self.duration_seconds / (self.distance_meters / 1000)

    @property
    def pace_label(self) -> str | None:
        pace = self.pace_seconds_per_km
        if not pace:
            return None
        minutes, seconds = divmod(round(pace), 60)
        return f"{minutes}:{seconds:02d} /km"
