"""`runserver` sans argument sert par défaut sur `APP_PORT` (5907, « sport »
en leet — voir CLAUDE.md) plutôt que sur le 8000 de Django. Un port explicite
en argument (`runserver 8001`) reste prioritaire, comme pour la commande
standard.
"""

from django.conf import settings
from django.contrib.staticfiles.management.commands.runserver import (
    Command as StaticfilesRunserverCommand,
)


class Command(StaticfilesRunserverCommand):
    default_port = str(settings.APP_PORT)
