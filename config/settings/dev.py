"""Réglages de développement local."""

from .base import *
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

INTERNAL_IPS = ["127.0.0.1"]
