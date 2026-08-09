"""Premier démarrage : rediriger vers la création du compte initial."""

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse


class FirstRunMiddleware:
    """Tant qu'aucun utilisateur n'existe, toute page mène à l'écran d'accueil.

    Sans cela, une installation neuve n'offrirait aucun moyen d'entrer : la
    connexion exige un compte, et la création d'un compte exige d'être connecté.

    Le contrôle s'arrête définitivement dès qu'un utilisateur est constaté —
    ce cas ne se produit qu'une fois par installation, il ne doit pas coûter une
    requête sur chaque appel.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self._bootstrapped = False

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not self._bootstrapped and self._needs_first_run(request):
            return redirect("accounts:first_run")
        return self.get_response(request)

    def _needs_first_run(self, request: HttpRequest) -> bool:
        from django.contrib.auth import get_user_model

        # Les chemins exemptés sont écartés AVANT toute requête : sans cela une
        # base injoignable ferait planter le middleware, et /healthz — dont le
        # rôle est précisément de signaler cette panne — ne répondrait plus.
        if self._is_exempt(request.path):
            return False

        if get_user_model().objects.exists():
            self._bootstrapped = True
            return False

        return True

    @staticmethod
    def _is_exempt(path: str) -> bool:
        exempt = (
            reverse("accounts:first_run"),
            reverse("core:healthz"),
            f"/{settings.STATIC_URL.lstrip('/')}",
            f"/{settings.MEDIA_URL.lstrip('/')}",
        )
        return path.startswith(exempt)
