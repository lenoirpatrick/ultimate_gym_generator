"""Réglages de la suite de tests.

SQLite en mémoire par défaut pour une exécution rapide sans service externe ;
la CI peut viser une vraie MariaDB en fournissant DATABASE_URL.
"""

import os

# Valeurs d'amorçage posées avant l'import de `base`, qui les exige.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("CREDENTIALS_ENCRYPTION_KEY", "dWx0aW1hdGUtZ3ltLWdlbmVyYXRvci10ZXN0LWtleSE=")

from .base import *
from .base import env

DEBUG = False

if not env.str("DATABASE_URL", default=""):
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

# Hachage rapide : les tests ne mesurent pas la robustesse de bcrypt.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
