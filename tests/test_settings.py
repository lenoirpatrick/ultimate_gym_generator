"""Résolution de la configuration d'environnement."""

import environ
import pytest
from django.core.exceptions import ImproperlyConfigured


def test_une_secret_key_manquante_empeche_le_demarrage(monkeypatch):
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
    env = environ.Env()

    with pytest.raises(ImproperlyConfigured):
        env.str("DJANGO_SECRET_KEY")


def test_database_url_est_traduite_en_reglages_django():
    parsed = environ.Env.db_url_config("mysql://gym:motdepasse@bdd.exemple.fr:3307/production")

    assert parsed["ENGINE"] == "django.db.backends.mysql"
    assert parsed["HOST"] == "bdd.exemple.fr"
    assert parsed["PORT"] == 3307
    assert parsed["NAME"] == "production"
    assert parsed["USER"] == "gym"


def test_le_port_par_defaut_est_5907():
    from django.conf import settings

    assert settings.APP_PORT == 5907


def test_runserver_sans_argument_ecoute_sur_le_port_de_l_application():
    """`manage.py runserver` seul démarrait sur le 8000 de Django plutôt que
    sur APP_PORT — la commande est surchargée pour les faire correspondre."""
    from django.conf import settings

    from core.management.commands.runserver import Command

    assert Command.default_port == str(settings.APP_PORT)


def test_le_cookie_de_session_dure_30_jours():
    """La valeur par défaut de Django (deux semaines) déconnectait trop tôt (#42)."""
    from django.conf import settings

    assert settings.SESSION_COOKIE_AGE == 60 * 60 * 24 * 30
