"""Amorçage d'une installation : compte initial, puis catalogue d'exercices."""

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse


class FirstRunMiddleware:
    """Tant que l'installation n'est pas amorcée, toute page mène à l'étape qui manque.

    Deux étapes, dans cet ordre : créer le premier compte, puis charger le
    catalogue d'exercices. Sans la première, une installation neuve n'offrirait
    aucun moyen d'entrer — la connexion exige un compte, et la création d'un
    compte exige d'être connecté. Sans la seconde, l'application fonctionnerait
    sans le référentiel sur lequel reposent les programmes.

    Le contrôle s'arrête définitivement une fois les deux étapes constatées :
    elles ne se produisent qu'une fois par installation et ne doivent pas coûter
    une requête sur chaque appel.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self._bootstrapped = False

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not self._bootstrapped and (destination := self._pending_step(request)):
            return redirect(destination)
        return self.get_response(request)

    def _pending_step(self, request: HttpRequest) -> str | None:
        """Route de l'étape d'amorçage à franchir, ou `None` s'il n'en reste aucune."""
        from django.contrib.auth import get_user_model

        from exercises import catalog

        # Les chemins exemptés sont écartés AVANT toute requête : sans cela une
        # base injoignable ferait planter le middleware, et /healthz — dont le
        # rôle est précisément de signaler cette panne — ne répondrait plus.
        if self._is_always_exempt(request.path):
            return None

        if not get_user_model().objects.exists():
            # Aucune exemption supplémentaire ici : tant qu'il n'existe pas de
            # compte, même la page de connexion n'a rien à proposer.
            return "accounts:first_run"

        if not catalog.is_loaded():
            # Le chargement exige un compte authentifié : la connexion doit
            # rester joignable, sinon la redirection boucle.
            if self._is_loading_exempt(request.path):
                return None
            return "exercises:loading"

        self._bootstrapped = True
        return None

    @staticmethod
    def _is_always_exempt(path: str) -> bool:
        exempt = (
            reverse("accounts:first_run"),
            reverse("core:healthz"),
            f"/{settings.STATIC_URL.lstrip('/')}",
            f"/{settings.MEDIA_URL.lstrip('/')}",
        )
        return path.startswith(exempt)

    @staticmethod
    def _is_loading_exempt(path: str) -> bool:
        exempt = (
            reverse("exercises:loading"),
            reverse("accounts:login"),
            reverse("accounts:logout"),
        )
        return path.startswith(exempt)
