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
        parser.add_argument(
            "--traduire",
            action="store_true",
            help="Traduit les consignes en français via le fournisseur IA actif (issue #29).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from aiproviders.clients import get_active_client

        translate = options["traduire"]
        if translate and get_active_client() is None:
            self.stdout.write(
                self.style.WARNING(
                    "Aucun fournisseur IA actif : les consignes resteront en anglais."
                )
            )

        try:
            if not options["force"] and not translate and catalog.is_loaded():
                total = catalog.progress().total
                self.stdout.write(f"Catalogue déjà chargé ({total} exercices). Rien à faire.")
                return

            imported = catalog.import_all(translate=translate)
        except catalog.CatalogError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"{imported} exercices chargés."))
