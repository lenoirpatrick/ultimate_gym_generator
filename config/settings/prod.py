"""Réglages de production.

Volontairement stricts : le déploiement échoue au démarrage plutôt que de
tourner dans une configuration non sûre.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *
from .base import ALLOWED_HOSTS, CREDENTIALS_ENCRYPTION_KEY, DB_PATH, DEBUG, env

if not CREDENTIALS_ENCRYPTION_KEY:
    raise ImproperlyConfigured(
        "CREDENTIALS_ENCRYPTION_KEY est obligatoire en production : sans elle, les "
        "credentials IA enregistrés sont illisibles."
    )

if DEBUG:
    raise ImproperlyConfigured("DJANGO_DEBUG doit valoir False en production.")

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS doit être renseigné en production.")

if not DB_PATH:
    raise ImproperlyConfigured(
        "DJANGO_DB_PATH est obligatoire en production : il doit pointer vers un volume "
        "persistant, sinon la base est perdue à chaque reconstruction de l'image."
    )

# Le terminaison TLS est généralement assurée par un reverse proxy en amont.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=31_536_000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# Cookies marqués Secure seulement quand la connexion l'est réellement : sans
# reverse proxy TLS devant (DJANGO_SECURE_SSL_REDIRECT=False), un navigateur
# rejette silencieusement tout cookie Secure reçu en HTTP simple — session et
# CSRF ne s'installent jamais, et la connexion échoue sans erreur visible.
SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
CSRF_COOKIE_SAMESITE = "Lax"

X_FRAME_OPTIONS = "DENY"
