#!/usr/bin/env python
"""Point d'entrée en ligne de commande de Django."""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - garde-fou d'installation
        raise ImportError(
            "Django est introuvable. Active l'environnement virtuel et installe "
            "les dépendances : pip install -r requirements/dev.txt"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
