from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def avatar_path(instance: "User", filename: str) -> str:
    """Range les avatars par utilisateur pour éviter les collisions de noms."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    return f"avatars/{instance.pk or 'nouveau'}/avatar.{extension}"


class User(AbstractUser):
    """Utilisateur de l'application.

    Modèle personnalisé posé dès la première migration : le remplacer plus tard
    imposerait une migration de données douloureuse.

    Les mesures corporelles sont facultatives — un compte reste utilisable sans
    elles — mais elles alimenteront le calcul des charges et des volumes
    d'entraînement. Toute donnée d'entraînement se rattache à un utilisateur.
    """

    class Gender(models.TextChoices):
        FEMALE = "F", "Femme"
        MALE = "M", "Homme"
        OTHER = "A", "Autre"
        UNDISCLOSED = "N", "Ne se prononce pas"

    email = models.EmailField("adresse e-mail", unique=True)

    avatar = models.ImageField("avatar", upload_to=avatar_path, blank=True, null=True)

    gender = models.CharField(
        "sexe",
        max_length=1,
        choices=Gender.choices,
        default=Gender.UNDISCLOSED,
        help_text="Utilisé pour adapter les recommandations d'entraînement.",
    )

    height_cm = models.PositiveSmallIntegerField(
        "taille (cm)",
        null=True,
        blank=True,
        validators=[MinValueValidator(90), MaxValueValidator(260)],
    )

    weight_kg = models.DecimalField(
        "poids (kg)",
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("25.0")), MaxValueValidator(Decimal("350.0"))],
    )

    class Meta(AbstractUser.Meta):
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def __str__(self) -> str:
        return self.get_full_name() or self.username

    @property
    def display_name(self) -> str:
        return self.get_short_name() or self.username

    @property
    def initials(self) -> str:
        """Repli affiché lorsque l'utilisateur n'a pas d'avatar."""
        parts = [self.first_name, self.last_name]
        letters = "".join(part[0] for part in parts if part)
        return (letters or self.username[:2]).upper()

    @property
    def bmi(self) -> Decimal | None:
        """Indice de masse corporelle, ou `None` si les mesures manquent."""
        if not self.height_cm or not self.weight_kg:
            return None
        metres = Decimal(self.height_cm) / Decimal(100)
        return (self.weight_kg / (metres * metres)).quantize(Decimal("0.1"))

    @property
    def has_body_metrics(self) -> bool:
        return bool(self.height_cm and self.weight_kg)
