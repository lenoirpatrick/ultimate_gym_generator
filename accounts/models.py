from decimal import Decimal
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from exercises.models import Exercise

#: Plafond de crans énumérés pour une charge réglable — voir `available_loads`.
MAX_LOAD_STEPS = 200


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


class UserEquipment(models.Model):
    """Matériel dont dispose un utilisateur, et charges qu'il permet.

    Sans cette déclaration, une séance ne peut proposer ni exercice réalisable
    ni charge crédible. Deux façons de décrire les charges, parce que les salles
    et les garages n'ont pas le même matériel : un jeu de charges figées
    (kettlebells, haltères d'un seul tenant) ou une plage réglable par crans
    (haltères à poids variables, barre chargée de disques).
    """

    class Mode(models.TextChoices):
        BODYWEIGHT = "bodyweight", "Sans charge"
        FIXED = "fixed", "Charges figées"
        ADJUSTABLE = "adjustable", "Charge réglable"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="equipment"
    )
    # Le référentiel de matériel est celui du catalogue : déclarer « haltères »
    # ici doit désigner exactement les exercices marqués « haltères » là-bas.
    equipment = models.CharField("matériel", max_length=16, choices=Exercise.Equipment.choices)
    mode = models.CharField("charges", max_length=12, choices=Mode.choices, default=Mode.BODYWEIGHT)

    weights = models.JSONField("charges disponibles", default=list, blank=True)

    min_kg = models.DecimalField(
        "charge minimale", max_digits=5, decimal_places=1, null=True, blank=True
    )
    max_kg = models.DecimalField(
        "charge maximale", max_digits=5, decimal_places=1, null=True, blank=True
    )
    step_kg = models.DecimalField(
        "incrément", max_digits=4, decimal_places=1, null=True, blank=True
    )

    class Meta:
        verbose_name = "matériel"
        verbose_name_plural = "matériel"
        # Dans l'ordre où le matériel a été déclaré, pas alphabétique : c'est
        # dans cet ordre que la ligne existe pour l'utilisateur qui l'a saisie.
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(fields=["user", "equipment"], name="unique_equipment_per_user")
        ]

    def __str__(self) -> str:
        return self.get_equipment_display()

    def available_loads(self) -> list[Decimal]:
        """Charges réellement disponibles, quel que soit le mode de description."""
        if self.mode == self.Mode.FIXED:
            return sorted(Decimal(str(weight)) for weight in self.weights or [])

        if self.mode == self.Mode.ADJUSTABLE and self.min_kg and self.max_kg and self.step_kg:
            loads = []
            charge = self.min_kg
            # Borne de sûreté : une plage large avec un pas minuscule produirait
            # des milliers de crans dont aucun ne servirait.
            while charge <= self.max_kg and len(loads) < MAX_LOAD_STEPS:
                loads.append(charge)
                charge += self.step_kg
            return loads

        return []
