"""Connexion à une instance Home Assistant et entités suivies (issue #129).

La connexion vaut pour toute l'installation, pas pour un utilisateur : elle se
règle depuis Configuration, réservée au personnel, comme les credentials IA.
"""

from dataclasses import dataclass

from django.core.validators import RegexValidator
from django.db import models

from aiproviders.fields import EncryptedTextField

#: Plafond d'entités suivies : au-delà, la page et surtout le bandeau du
#: minuteur cesseraient de se lire d'un coup d'œil.
MAX_ENTITIES = 5


@dataclass(frozen=True)
class EntityAction:
    """Service Home Assistant proposé en bouton sur une entité."""

    service: str
    label: str


#: Actions par domaine d'entité — déduites, jamais saisies : un service mal
#: orthographié ne doit pas pouvoir se configurer. Un domaine absent de cette
#: table (capteur, etc.) est en lecture seule. Pas de « basculer » : la carte
#: ne propose que l'action qui change l'état courant (`Entity.actions_for`).
_SWITCHABLE = (
    EntityAction("turn_on", "Allumer"),
    EntityAction("turn_off", "Éteindre"),
)
DOMAIN_ACTIONS: dict[str, tuple[EntityAction, ...]] = {
    "switch": _SWITCHABLE,
    "light": _SWITCHABLE,
    "fan": _SWITCHABLE,
    "input_boolean": _SWITCHABLE,
    "scene": (EntityAction("turn_on", "Activer"),),
    "script": (EntityAction("turn_on", "Lancer"),),
    "button": (EntityAction("press", "Appuyer"),),
    "input_button": (EntityAction("press", "Appuyer"),),
}


class Connection(models.Model):
    """Adresse de l'instance et jeton d'accès longue durée — une seule ligne."""

    base_url = models.URLField(
        "adresse de l'instance",
        max_length=200,
        help_text="Par exemple http://homeassistant.local:8123",
    )
    token = EncryptedTextField("jeton d'accès longue durée")
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "connexion Home Assistant"
        verbose_name_plural = "connexion Home Assistant"

    def __str__(self) -> str:
        return self.base_url

    @classmethod
    def load(cls) -> "Connection | None":
        """La connexion enregistrée, `None` tant qu'aucune ne l'est."""
        return cls.objects.first()

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.token)


class Entity(models.Model):
    """Entité Home Assistant suivie, et où l'afficher : en aperçu sur l'écran
    d'une séance, dans le minuteur une fois lancée, ou les deux."""

    entity_id = models.CharField(
        "identifiant",
        max_length=255,
        unique=True,
        validators=[
            RegexValidator(
                r"^[a-z_]+\.[a-z0-9_]+$",
                "Identifiant Home Assistant attendu, par exemple switch.ventilateur.",
            )
        ],
    )
    label = models.CharField("libellé", max_length=60)
    show_on_workout = models.BooleanField("afficher sur la séance", default=True)
    show_in_timer = models.BooleanField("afficher dans le minuteur", default=False)

    class Meta:
        verbose_name = "entité Home Assistant"
        verbose_name_plural = "entités Home Assistant"
        # Ordre de déclaration, comme le matériel : celui dans lequel le
        # personnel les a pensées.
        ordering = ("id",)

    def __str__(self) -> str:
        return self.label

    @property
    def domain(self) -> str:
        return self.entity_id.split(".", 1)[0]

    @property
    def actions(self) -> tuple[EntityAction, ...]:
        return DOMAIN_ACTIONS.get(self.domain, ())

    def actions_for(self, state: str | None) -> tuple[EntityAction, ...]:
        """Actions utiles dans l'état courant : « Allumer » ne sert à rien sur
        une lumière déjà allumée. Un état inconnu garde les deux, faute de
        savoir lequel serait sans effet."""
        useless = {"on": "turn_on", "off": "turn_off"}.get(state or "")
        return tuple(action for action in self.actions if action.service != useless)


def _configured() -> bool:
    """Connexion renseignée, sans déchiffrer le jeton : la question est
    seulement de savoir s'il y a quelque chose à montrer, et une clé de
    chiffrement absente ne doit pas faire échouer l'écran de séance."""
    return Connection.objects.exclude(base_url="").exclude(token="").exists()


def workout_entities() -> list[Entity]:
    """Entités en aperçu sur l'écran d'une séance (issue #133), vide sans connexion."""
    if not _configured():
        return []
    return list(Entity.objects.filter(show_on_workout=True))
