"""Chargement du catalogue d'exercices en une passe.

Destiné au déploiement et à l'automatisation ; les installations interactives
passent par l'écran de chargement, qui affiche l'avancement.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from exercises import catalog


class Command(BaseCommand):
    help = "Charge le catalogue d'exercices en base (idempotent)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Réimporte même si le catalogue est déjà complet.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            if not options["force"] and catalog.is_loaded():
                total = catalog.progress().total
                self.stdout.write(f"Catalogue déjà chargé ({total} exercices). Rien à faire.")
                return

            imported = catalog.import_all()
        except catalog.CatalogError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"{imported} exercices chargés."))
