"""Champ de modèle chiffré au repos.

Les clés d'API des fournisseurs d'IA sont chiffrées avec Fernet avant d'atteindre
la base : une copie du dump SQL ne suffit pas à les exploiter. La clé de
chiffrement vit dans l'environnement (`CREDENTIALS_ENCRYPTION_KEY`), jamais en base.

Conséquence assumée : le contenu chiffré n'est pas déterministe, on ne peut donc
ni filtrer ni indexer sur ce champ. Ce n'est pas une limite gênante pour un secret.
"""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = settings.CREDENTIALS_ENCRYPTION_KEY
    if not key:
        raise ImproperlyConfigured(
            "CREDENTIALS_ENCRYPTION_KEY n'est pas renseignée : impossible de lire ou "
            "d'écrire un credential IA."
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            "CREDENTIALS_ENCRYPTION_KEY n'est pas une clé Fernet valide. En générer une : "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        ) from exc


class DecryptionError(Exception):
    """La valeur en base n'a pas pu être déchiffrée avec la clé courante."""


class EncryptedTextField(models.TextField):
    """TextField dont la valeur est chiffrée en base et déchiffrée à la lecture."""

    def get_prep_value(self, value: str | None) -> str | None:
        if value in (None, ""):
            return value
        return _fernet().encrypt(str(value).encode()).decode()

    def from_db_value(self, value, expression, connection) -> str | None:
        if value in (None, ""):
            return value
        try:
            return _fernet().decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise DecryptionError(
                "Déchiffrement impossible : CREDENTIALS_ENCRYPTION_KEY a probablement "
                "changé depuis l'enregistrement. Restaurer l'ancienne clé ou ressaisir "
                "les credentials."
            ) from exc
