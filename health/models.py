"""Données de santé importées depuis Apple HealthKit.

Un export Apple Health classique ne porte aucun identifiant stable par
enregistrement — contrairement au catalogue d'exercices, qui a un `slug`.
L'unicité s'appuie donc sur une clé naturelle : l'instant de la mesure pour un
poids, le début de l'activité pour une séance. Un réimport met donc à jour la
ligne existante plutôt que d'en créer une seconde (issue #70).
"""

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils.crypto import get_random_string


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
    # Durée active HealthKit (attribut `duration`), pas `ended_at - started_at` :
    # une séance mise en pause (feu rouge, calibrage GPS…) dure plus longtemps en
    # horloge murale que son temps d'effort réel, faussant durée et allure d'un
    # facteur proche de 2 dans les cas observés (issue #79). Repli sur l'écart
    # horaire seulement si l'attribut HealthKit est absent (import#70) ou pour une
    # activité créée via l'API (#71), qui ne le transmet pas forcément.
    duration_seconds = models.PositiveIntegerField("durée (s)")
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

    def save(self, *args, **kwargs) -> None:
        # Repli centralisé, plutôt que dupliqué chez chaque appelant
        # (`health.ingest`, tests) : sans durée active connue, l'écart horaire
        # reste la meilleure approximation disponible.
        if self.duration_seconds is None:
            self.duration_seconds = max(0, int((self.ended_at - self.started_at).total_seconds()))
        super().save(*args, **kwargs)

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
    def calories_label(self) -> str | None:
        if not self.active_energy_kcal:
            return None
        return f"{round(self.active_energy_kcal)} kcal"

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


class DailySteps(models.Model):
    """Total de pas d'une journée (issue #75).

    Apple Health exporte les pas en une multitude de petits intervalles
    (toutes les quelques minutes), jamais un total par jour — `health.importer`
    les agrège avant d'écrire ici. La clé naturelle est donc la date, pas
    l'instant : un réimport recalcule et remplace le total du jour plutôt que
    de l'additionner une seconde fois.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_steps",
        verbose_name="utilisateur",
    )
    date = models.DateField("date")
    steps = models.PositiveIntegerField("pas")

    class Meta:
        verbose_name = "total de pas quotidien"
        verbose_name_plural = "totaux de pas quotidiens"
        ordering = ("-date",)
        constraints = [models.UniqueConstraint(fields=["user", "date"], name="unique_daily_steps")]

    def __str__(self) -> str:
        return f"{self.steps} pas — {self.date:%d/%m/%Y}"


class ApiKey(models.Model):
    """Clé d'accès à l'API d'ingestion (#71), propre à un utilisateur.

    Hachée à sens unique (`make_password`, comme un mot de passe) plutôt que
    chiffrée : contrairement aux credentials IA d'`aiproviders`, qui doivent
    être relus en clair pour appeler un fournisseur, cette clé n'a jamais
    besoin d'être redéchiffrée — seulement vérifiée. Elle n'est donc montrée
    qu'une fois, à la création.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="health_api_keys",
        verbose_name="utilisateur",
    )
    label = models.CharField("nom", max_length=120)
    prefix = models.CharField("préfixe", max_length=8, unique=True, db_index=True)
    hashed_key = models.CharField("clé (hachée)", max_length=128)
    created_at = models.DateTimeField("créée le", auto_now_add=True)
    last_used_at = models.DateTimeField("dernière utilisation", null=True, blank=True)

    class Meta:
        verbose_name = "clé API"
        verbose_name_plural = "clés API"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.label} ({self.prefix}…)"

    @classmethod
    def generate(cls, user, label: str) -> tuple["ApiKey", str]:
        """Crée une clé et renvoie la valeur en clair — à afficher une seule fois."""
        raw_key = get_random_string(43)
        prefix = raw_key[:8]
        instance = cls.objects.create(
            user=user, label=label, prefix=prefix, hashed_key=make_password(raw_key)
        )
        return instance, raw_key

    def matches(self, raw_key: str) -> bool:
        return check_password(raw_key, self.hashed_key)
