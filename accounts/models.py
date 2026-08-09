from decimal import Decimal
from typing import Any

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def avatar_path(instance: "User", filename: str) -> str:
    """Range les avatars par utilisateur pour éviter les collisions de noms."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    return f"avatars/{instance.pk or 'nouveau'}/avatar.{extension}"


class UserManager(BaseUserManager):
    """Crée les comptes à partir de l'adresse e-mail, seul identifiant de connexion.

    Remplace le gestionnaire de Django, dont la signature commence par un nom
    d'utilisateur que ce modèle n'a plus.
    """

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields: Any) -> "User":
        if not email:
            raise ValueError("Une adresse e-mail est obligatoire.")

        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> "User":
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("Un superutilisateur est nécessairement membre du personnel.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Utilisateur de l'application.

    Modèle personnalisé posé dès la première migration : le remplacer plus tard
    imposerait une migration de données douloureuse.

    L'adresse e-mail est le seul identifiant de connexion : `username` est
    retiré plutôt que conservé en doublon, pour qu'aucun écran n'ait à demander
    lequel des deux saisir.

    Les mesures corporelles sont facultatives — un compte reste utilisable sans
    elles — mais elles alimenteront le calcul des charges et des volumes
    d'entraînement. Toute donnée d'entraînement se rattache à un utilisateur.
    """

    class Gender(models.TextChoices):
        FEMALE = "F", "Femme"
        MALE = "M", "Homme"
        OTHER = "A", "Autre"
        UNDISCLOSED = "N", "Ne se prononce pas"

    username = None

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

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta(AbstractUser.Meta):
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def __str__(self) -> str:
        return self.get_full_name() or self.email

    def save(self, *args: Any, **kwargs: Any) -> None:
        # L'identifiant de connexion ne doit pas dépendre de la casse saisie :
        # sans cette normalisation, `Coach@x.test` et `coach@x.test` seraient
        # deux comptes distincts sur un moteur sensible à la casse, et une
        # majuscule involontaire suffirait à faire échouer une connexion.
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        return self.get_short_name() or self.email

    @property
    def initials(self) -> str:
        """Repli affiché lorsque l'utilisateur n'a pas d'avatar."""
        parts = [self.first_name, self.last_name]
        letters = "".join(part[0] for part in parts if part)
        return (letters or self.email[:2]).upper()

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
