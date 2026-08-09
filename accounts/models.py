from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Utilisateur de l'application.

    Modèle personnalisé posé dès la première migration : le remplacer plus tard
    imposerait une migration de données douloureuse. Les champs propres au
    domaine sportif (objectifs, niveau, matériel disponible) viendront s'ajouter
    ici ou dans un profil dédié.
    """

    email = models.EmailField("adresse e-mail", unique=True)

    class Meta(AbstractUser.Meta):
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def __str__(self) -> str:
        return self.get_full_name() or self.username
