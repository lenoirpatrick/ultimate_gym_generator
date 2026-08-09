"""Réglages communs à tous les environnements.

Toute valeur qui change d'un déploiement à l'autre est lue dans l'environnement
(fichier `.env` en local, variables d'environnement en conteneur). Aucun secret
n'est écrit en dur ici.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env()
env.read_env(BASE_DIR / ".env")

# --------------------------------------------------------------------------- #
# Sécurité
# --------------------------------------------------------------------------- #

SECRET_KEY = env.str("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# Clé Fernet servant à chiffrer les credentials IA stockés en base. La générer avec :
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#
# Facultative ici pour que les commandes hors-ligne (collectstatic pendant un
# build d'image) n'aient pas besoin d'un secret. Toute manipulation réelle d'un
# credential lève alors une erreur explicite, et `config.settings.prod` exige
# sa présence au démarrage.
CREDENTIALS_ENCRYPTION_KEY = env.str("CREDENTIALS_ENCRYPTION_KEY", default="")

# Port d'écoute de l'application (5907 = « sport » en leet).
APP_PORT = env.int("DJANGO_PORT", default=5907)

# Déplaçable pour réduire la surface d'attaque d'un déploiement exposé.
ADMIN_URL = env.str("DJANGO_ADMIN_URL", default="admin/")

# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "aiproviders",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
            ],
        },
    },
]

# --------------------------------------------------------------------------- #
# Base de données
#
# Deux modes, sans changement de code :
#   1. MariaDB fournie par docker-compose  -> valeurs DB_* par défaut
#   2. MariaDB externe                     -> renseigner DATABASE_URL
# Voir docs/INSTALL.md.
# --------------------------------------------------------------------------- #


def _database_config() -> dict:
    """Résout la base à utiliser, par ordre de priorité décroissant."""
    if url := env.str("DATABASE_URL", default=""):
        return env.db_url_config(url)

    if host := env.str("DB_HOST", default=""):
        return {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env.str("DB_NAME", default="gym"),
            "USER": env.str("DB_USER", default="gym"),
            "PASSWORD": env.str("DB_PASSWORD", default=""),
            "HOST": host,
            "PORT": env.int("DB_PORT", default=3306),
        }

    # Aucune base déclarée : SQLite, pour démarrer en local sans rien installer.
    # `config.settings.prod` refuse ce cas.
    return {"ENGINE": "django.db.backends.sqlite3", "NAME": str(BASE_DIR / "db.sqlite3")}


DATABASES = {"default": _database_config()}
DATABASES["default"].setdefault("OPTIONS", {})
if DATABASES["default"]["ENGINE"] == "django.db.backends.mysql":
    DATABASES["default"]["OPTIONS"].update(
        {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        }
    )
    DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------- #
# Authentification
# --------------------------------------------------------------------------- #

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "core:home"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------- #
# Internationalisation
# --------------------------------------------------------------------------- #

LANGUAGE_CODE = env.str("DJANGO_LANGUAGE_CODE", default="fr-fr")
TIME_ZONE = env.str("DJANGO_TIME_ZONE", default="Europe/Paris")
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------- #
# Fichiers statiques
# --------------------------------------------------------------------------- #

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --------------------------------------------------------------------------- #
# Journalisation
# --------------------------------------------------------------------------- #

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s :: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": env.str("DJANGO_LOG_LEVEL", default="INFO")},
}
